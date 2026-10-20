import json
from pathlib import Path

import numpy as np
import pytest
from maa.custom_recognition import CustomRecognition


ROOT = Path(__file__).resolve().parents[1]


def test_vr_uses_free_quota_instead_of_one_daily_completion(pipelines):
    spend = pipelines["Daily_VRSpend"]
    assert spend["max_hit"] == 9
    assert spend["anchor"]["Daily_AfterReward"] == "DailyVR_AfterReward"
    assert spend["on_error"] == ["Daily_StopCapture"]
    entry = pipelines["DailyVR_Start"]
    assert entry["anchor"]["NavHome_Return"] == "DailyCore_Quest"
    assert entry["anchor"]["DailyCore_QuestTarget"] == "DailyVR_Open"


def run_quota(native, pipelines, quota, updates=(), cap=9, entry="Daily_VRMainOpen"):
    remaining, clicks, updates = [quota], [], list(updates)

    class Quota(CustomRecognition):
        def analyze(self, context, argv):
            params = json.loads(argv.custom_recognition_param)
            match = (remaining[0] == params["exact"] if "exact" in params else
                     type(remaining[0]) is int and remaining[0] > 0)
            return (0, 0, 1, 1) if match else None

    assert native.resource.register_custom_recognition("OfflineQuota", Quota())

    def click(x, y):
        assert remaining[0] > 0, "Zero quota must never authorize a paid click"
        remaining[0] = updates.pop(0) if updates else remaining[0] - 1
        clicks.append((x, y))
        return True

    native.controller.on_click = click
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 20, "rate_limit": 1}
                 for name in pipelines}
    overrides["DailyVR_Start"] = {**pipelines.get("DailyVR_Start", {}),
                                  "recognition": "DirectHit", "next": [entry], "post_delay": 0}
    overrides["Daily_VRMainOpen"].update(recognition="DirectHit", action="DoNothing")
    overrides["Daily_VRSpend"].update(recognition="Custom", custom_recognition="OfflineQuota",
                                       custom_recognition_param={}, max_hit=cap, next=["DailyVR_AfterReward"])
    for number in range(10):
        for prefix in ("Read", "Verify"):
            name = f"DailyVR_{prefix}{number}"
            if name in pipelines:
                overrides[name].update(recognition="Custom", custom_recognition="OfflineQuota",
                                       custom_recognition_param={"exact": number})
    overrides["DailyVR_Exhausted"] = {"recognition": "Custom", "custom_recognition": "OfflineQuota",
                                      "custom_recognition_param": {"exact": 0}, "next": ["Daily_Return"]}
    overrides["Daily_Return"] = {"recognition": "DirectHit", "next": ["Daily_OnHome"], "post_delay": 0}
    overrides["Daily_OnHome"] = {"recognition": "DirectHit", "post_delay": 0}
    overrides["DailyCore_Done"] = {"recognition": "DirectHit", "post_delay": 0}
    overrides["Daily_StopCapture"]["action"] = "DoNothing"
    names = [item.name for item in native.run("DailyVR_Start", overrides).nodes]
    return names, clicks


@pytest.mark.parametrize("quota,cap,expected,stopped", [(0, 9, 0, False), (1, 9, 1, False),
    (2, 9, 2, False), (9, 9, 9, False), (9, 3, 3, True), (11, 9, 0, True), (None, 9, 0, True)])
def test_vr_rechecks_quota_and_stops_before_paid_or_unbounded_repeats(native, pipelines, quota, cap, expected, stopped):
    names, clicks = run_quota(native, pipelines, quota, cap=cap)
    assert len(clicks) == expected
    assert names[-1] == ("Daily_Stop" if stopped else "DailyCore_Done")
    assert not any(name in ("Daily_Claim", "Daily_MilestoneClaim", "Daily_GoldSpend") for name in names)


@pytest.mark.parametrize("after", [3, 1, 4, None])
def test_vr_requires_exactly_one_free_quota_decrease_before_another_skip(native, pipelines, after):
    names, clicks = run_quota(native, pipelines, 3, updates=[after])
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"


def test_vr_cannot_continue_after_rewards_without_a_pre_spend_counter(native, pipelines):
    names, clicks = run_quota(native, pipelines, 3, entry="DailyVR_AfterReward")
    assert not clicks and names[-1] == "Daily_Stop"


def test_vr_positive_quota_requires_the_free_skip_control(native):
    if not all((ROOT / "assets/resource/model/ocr" / name).is_file()
               for name in ("det.onnx", "rec.onnx", "keys.txt")):
        pytest.skip("Native OCR models are not provisioned")
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/daily/controls.npz", allow_pickle=False) as crops:
        for key, (x, y) in {"vr_title": (51, 42), "vr_free2": (509, 1027)}.items():
            crop = crops[key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    assert native.match("Daily_VRSpend", image)
    assert native.match("DailyVR_Read2", image) and native.match("DailyVR_Verify2", image)
    assert not native.match("DailyVR_Read1", image) and not native.match("DailyVR_Verify1", image)
    assert not native.match("Daily_VRSpend", (image * 0.75).astype(np.uint8))
    image[1031:1060, 615:658] = 0
    assert not native.match("Daily_VRSpend", image)
