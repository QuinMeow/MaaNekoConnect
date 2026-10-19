import json
from types import SimpleNamespace

import numpy as np
import pytest
from maa.custom_recognition import CustomRecognition

from agent import recovery


REGIONS = {
    "network_message": (185, 508, 350, 54), "network_confirm": (211, 635, 298, 62),
    "title_tap": (248, 1064, 225, 32), "title_logo": (219, 955, 283, 34),
    "loading_text": (549, 1198, 108, 27), "home_building": (535, 1105, 140, 110),
    "home_text": (530, 1205, 155, 65),
}


def analyze(context, raw="{}", image=None):
    argv = SimpleNamespace(custom_recognition_param=raw, roi=(0, 0, 16, 16),
                           image=np.ones((16, 16, 3), dtype=np.uint8) if image is None else image)
    return recovery.WaitForFrozenScreen().analyze(context, argv)


@pytest.mark.parametrize("result", [True, False, None, 0, 1, "true"])
def test_only_boolean_true_authorizes_frozen_recognition(result):
    context = SimpleNamespace(wait_freezes=lambda **kwargs: result)
    assert (analyze(context) is not None) is (result is True)


@pytest.mark.parametrize("raw", [
    "not JSON", "null", "[]", '{"time":true}', '{"time":0}', '{"timeout":-1}',
    '{"time":20,"timeout":10}', '{"rate_limit":40000}', '{"method":2}',
    '{"target":[0,0,-1,1]}', '{"threshold":NaN}', '{"threshold":2}', '{"extra":1}',
])
def test_invalid_params_never_wait(raw):
    context = SimpleNamespace(wait_freezes=lambda **kwargs: pytest.fail("Invalid wait"))
    assert analyze(context, raw) is None


def test_callback_errors_and_invalid_images_fail_closed():
    def fail(**kwargs):
        raise RuntimeError("native wait failed")
    assert analyze(SimpleNamespace(wait_freezes=fail)) is None
    assert analyze(SimpleNamespace(), image=np.empty((0, 0, 3), dtype=np.uint8)) is None


@pytest.mark.parametrize("case,expected", [
    ("black", True), ("changed", False), ("failed", False), ("stopped", False), ("late", False),
])
def test_black_exception_needs_fresh_continuous_frames_and_respects_stop(monkeypatch, case, expected):
    now, captures = [0.0], []
    image = np.zeros((16, 16, 3), dtype=np.uint8)
    controller = SimpleNamespace(cached_image=image)
    tasker = SimpleNamespace(controller=controller, stopping=case == "stopped")

    def capture():
        captures.append(True)
        if case == "changed":
            controller.cached_image = np.ones_like(image)
        if case == "late":
            now[0] += 1
        return SimpleNamespace(wait=lambda: SimpleNamespace(succeeded=case != "failed"))

    controller.post_screencap = capture
    monkeypatch.setattr(recovery.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(recovery.time, "sleep", lambda seconds: now.__setitem__(0, now[0] + seconds))
    result = analyze(SimpleNamespace(tasker=tasker),
                     '{"time":20,"timeout":50,"rate_limit":10}', image)
    assert (result is not None) is expected
    assert bool(captures) is (case != "stopped")


@pytest.mark.parametrize("moving", [False, True])
def test_native_wait_distinguishes_static_and_moving_frames(native, moving):
    rng = np.random.default_rng(7)
    image = rng.integers(1, 256, (1280, 720, 3), dtype=np.uint8)
    native.controller.source = lambda: rng.integers(1, 256, image.shape, dtype=np.uint8) if moving else image
    recovery.register_recovery(native.resource)
    assert native.resource.override_pipeline({"CommonFrozen30": {"custom_recognition_param": {
        "time": 100, "timeout": 300, "rate_limit": 20, "threshold": 0.000001,
    }}})
    assert native.match("CommonFrozen30", image) is not moving


@pytest.mark.parametrize("sample,node", [
    ("network_stable", "CommonNetworkConfirm"), ("title_truck", "CommonTitleTap"),
    ("title_characters", "CommonTitleTap"), ("title_loading", "CommonLoading"),
    ("enhance_loading", "CommonLoading"), ("home_ready_holdout", "CommonHomeReady"),
])
def test_observed_recovery_states_and_blank_negatives(native, frame, sample, node):
    assert native.match(node, frame("recovery", sample, REGIONS))
    assert not native.match(node, np.zeros((1280, 720, 3), dtype=np.uint8))


@pytest.mark.parametrize("region", ["network_message", "network_confirm"])
def test_network_click_requires_both_markers(native, frame, region):
    image = frame("recovery", "network_stable", REGIONS)
    x, y, width, height = REGIONS[region]
    image[y:y + height, x:x + width] = 0
    assert not native.match("CommonNetworkConfirm", image)


def test_recovery_contract_keeps_bounds_freshness_and_exact_package(pipelines):
    for name, limit in (("CommonRecoveryBudget", 3), ("CommonRecoveryWatchPermit", 3),
                        ("CommonRecoveryRestartPermit", 2)):
        assert pipelines[name]["max_hit"] == limit
    for name in ("CommonRecoveryDispatch", "CommonRecoveryFreshCheck"):
        targets = pipelines[name]["next"]
        loading = "CommonRecoveryLoading" if name.endswith("Dispatch") else "CommonFrozenLoading"
        assert targets.index(loading) < targets.index("CommonTitleTap")
    assert pipelines["CommonFrozen30"]["next"] == ["CommonRecoveryFreshCheck"]
    assert pipelines["CommonRecoveryRecovered"]["next"] == ["[Anchor]CommonRecoveryResume"]
    for name, node in pipelines.items():
        if name.startswith("Common"):
            assert not any("FurnitureEnhance_Start" in target for target in node.get("next", []))
            assert not any("Permit" in anchor for anchor in node.get("anchor", {}))
            if node.get("action") in ("StartApp", "StopApp"):
                assert node["package"] == "jp.goodsmile.nekoconne"


@pytest.mark.parametrize("reveal,expected_restarts", [(False, 2), (True, 0)])
def test_recovery_rechecks_after_freeze_and_bounds_persistent_restarts(
    native, pipelines, frame, reveal, expected_restarts,
):
    calls = []
    controller = native.controller
    home = frame("recovery", "home_ready_holdout", REGIONS)

    class Frozen(CustomRecognition):
        def analyze(self, context, argv):
            if reveal:
                controller.image = home
            return (0, 0, 1, 1)

    assert native.resource.register_custom_recognition("WaitForFrozenScreen", Frozen())
    controller.on_stop = lambda package: calls.append(("stop", package)) or True
    controller.on_start = lambda package: calls.append(("start", package)) or True
    overrides = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 50, "rate_limit": 1}
                 for name in pipelines}
    for name in ("CommonRecoveryBeforeRestart", "CommonRecoveryStopCapture"):
        overrides[name]["action"] = "DoNothing"
    overrides["TestRecovery"] = {"recognition": "DirectHit", "post_delay": 0,
                                 "anchor": {"CommonRecoveryResume": "TestDone"},
                                 "next": ["CommonRecoveryEnter"]}
    overrides["TestDone"] = {"recognition": "DirectHit", "post_delay": 0, "next": []}
    names = [node.name for node in native.run("TestRecovery", overrides).nodes]
    assert calls == [(kind, "jp.goodsmile.nekoconne")
                     for _ in range(expected_restarts) for kind in ("stop", "start")]
    assert names[-1] == ("TestDone" if reveal else "CommonRecoveryStop")
