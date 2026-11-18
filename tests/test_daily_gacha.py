from pathlib import Path

import numpy as np
import pytest
from maa.custom_action import CustomAction


ROOT = Path(__file__).resolve().parents[1]
REGIONS = {
    "title": (35, 25, 125, 60), "free": (255, 995, 220, 50),
    "remaining": (270, 1121, 190, 31), "confirm_title": (220, 337, 285, 42),
    "confirm_free": (420, 780, 200, 36), "confirm_count": (490, 815, 60, 45),
    "confirm_button": (395, 820, 245, 35),
}


def image(sample):
    result = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/daily_gacha" / f"{sample}.npz", allow_pickle=False) as crops:
        for name in crops.files:
            x, y, width, height = REGIONS[name]
            assert crops[name].shape == (height, width, 3)
            result[y:y + height, x:x + width] = crops[name]
    return result


def test_free_ad_requires_native_positive_count_and_advertisement_label(native):
    frame = image("free")
    assert native.match("DailyGacha_AdReady", frame)
    frame[1121:1152, 270:460] = 0
    assert not native.match("DailyGacha_AdReady", frame), "Unknown free quota never permits a draw"
    frame = image("free")
    frame[995:1045, 255:475] = 0
    assert not native.match("DailyGacha_AdReady", frame), "Gem/ticket banners are not advertisement draws"


def test_confirmation_requires_ad_title_free_price_and_bright_red_button(native):
    frame = image("confirm")
    assert native.match("DailyGacha_ConfirmGuard", frame)
    frame[780:816, 420:620] = 0
    assert not native.match("DailyGacha_ConfirmGuard", frame)
    assert not native.match("DailyGacha_ConfirmGuard", (image("confirm") * 0.7).astype(np.uint8))


def test_unknown_ad_result_never_replays_the_trigger(pipelines):
    spend = pipelines["DailyGacha_AdSpend"]
    assert spend["max_hit"] == 1 and spend["on_error"] == ["Daily_StopCapture"]
    assert spend["anchor"]["CommonRecoveryResume"] == "Daily_StopCapture"
    poll = pipelines["DailyGacha_AdPoll"]["next"]
    assert "DailyGacha_GameStillVisible" in poll
    assert poll.index("DailyGacha_GameStillVisible") < poll.index("DailyGacha_AdStep")
    for name in ("DailyGacha_AdPoll", "DailyGacha_AdStep", "DailyGacha_GameStillVisible"):
        assert "DailyGacha_AdSpend" not in pipelines[name].get("next", [])


def test_banner_guard_is_not_satisfied_by_paid_confirm(native):
    assert not native.match("DailyGacha_AdReady", image("confirm"))
    assert not native.match("DailyGacha_ConfirmGuard", image("free"))


def test_disabled_native_close_placeholder_waits_without_clicking(native, monkeypatch):
    from types import SimpleNamespace
    from agent import ad_close

    monkeypatch.setattr(ad_close, "load_config", lambda: None)
    outcomes = []

    class Probe(CustomAction):
        def run(self, context, argv):
            control = ad_close.AdCloseControl()
            for _ in range(41):
                outcomes.append(control.run(context, SimpleNamespace(custom_action_param="{}")))
            return True

    assert native.resource.register_custom_action("ProbeAdWait", Probe())
    native.run("TestAdWait", {"TestAdWait": {
        "action": "Custom", "custom_action": "ProbeAdWait", "post_delay": 0}})
    assert outcomes == [True] * 40 + [False]


def test_missing_ai_settings_stop_before_entering_advertisement(native, monkeypatch):
    from agent import ad_close

    monkeypatch.setattr(ad_close, "load_config", lambda: None)
    ad_close.register_ad_close(native.resource)
    names = [node.name for node in native.run("DailyGacha_ConfigCheck", {
        "Daily_StopCapture": {"action": "DoNothing", "post_delay": 0},
    }).nodes]
    assert names[-1] == "Daily_Stop" and "DailyGacha_AdSpend" not in names


def test_slow_sdk_confirmation_waits_bounded_without_replaying_draw(native, pipelines):
    checks = []

    class DelayedSDK(CustomAction):
        def run(self, context, argv):
            checks.append(True)
            context.override_pipeline({"DailyGacha_ConfirmStillVisible": {"enabled": False},
                                       "DailyGacha_AdQuotaConsumed": {"recognition": "DirectHit"}})
            return True

    native.resource.register_custom_action("DelayedSDK", DelayedSDK())
    patch = {name: {"post_delay": 0, "timeout": 20, "rate_limit": 1} for name in pipelines}
    patch["DailyGacha_ConfirmGuard"].update(recognition="DirectHit")
    patch["DailyGacha_WaitForSDK"].update(action="Custom", custom_action="DelayedSDK")
    patch["DailyGacha_AdQuotaConsumed"].update(action="DoNothing", next=[])
    patch["Daily_PostError"].update(enabled=False)
    patch["Daily_StopCapture"].update(action="DoNothing")
    names = [node.name for node in native.run("DailyGacha_ConfirmStillVisible", patch).nodes]
    assert checks and names[-1] == "DailyGacha_AdQuotaConsumed"
    assert "DailyGacha_AdSpend" not in names and "Daily_Stop" not in names
    assert 1 <= pipelines["DailyGacha_WaitForSDK"]["max_hit"] <= 10
