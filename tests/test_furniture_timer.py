import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from maa.custom_action import CustomAction

from agent import furniture_timer as timer


def run(context, op, **params):
    return timer.FurnitureTimerControl().run(
        context, SimpleNamespace(custom_action_param=json.dumps({"op": op, **params})),
    )


@pytest.fixture
def context(monkeypatch):
    ctx = SimpleNamespace(now=100.0, nodes={}, anchors={}, frozen=False, after_freeze=None,
                          hits={"FurnitureEnhance_PageGuard", "FurnitureEnhance_ReadyPreview"},
                          ocr={"best": {"text": "00:01:20", "score": 0.99}})
    ctx.tasker = SimpleNamespace(stopping=False, controller=SimpleNamespace(
        cached_image=np.ones((1280, 720, 3), dtype=np.uint8),
        post_screencap=lambda: SimpleNamespace(wait=lambda: SimpleNamespace(succeeded=True)),
    ))
    ctx.get_node_data = lambda name: deepcopy(ctx.nodes.get(name))
    ctx.override_pipeline = lambda update: ctx.nodes.update(deepcopy(update)) or True
    ctx.set_anchor = lambda name, target: ctx.anchors.update({name: target}) or True
    ctx.run_recognition = Mock(side_effect=lambda name, image: SimpleNamespace(
        hit=True, raw_detail=ctx.ocr,
    ) if name == "FurnitureTimer_OCR" else SimpleNamespace(hit=name in ctx.hits))

    def freeze(*, wait_freezes_param):
        ctx.now += (wait_freezes_param.time if ctx.frozen else wait_freezes_param.timeout) / 1000
        if ctx.after_freeze:
            ctx.hits = ctx.after_freeze
        return ctx.frozen

    ctx.wait_freezes = Mock(side_effect=freeze)
    monkeypatch.setattr(timer.time, "monotonic", lambda: ctx.now)
    monkeypatch.setattr(timer.time, "sleep", lambda seconds: setattr(ctx, "now", ctx.now + seconds))
    return ctx


@pytest.mark.parametrize("text,score,expected", [
    ("00:07:58", 0.9, 478), ("99:59:59", 1, 359999), ("7:58", 1, None),
    ("00:60:00", 1, None), ("00:00:60", 1, None), ("00:07:58x", 1, None),
    ("00:07:58", 0.89, None), ("00:07:58", True, None), ("00:07:58", float("nan"), None),
])
def test_countdown_requires_strict_format_and_finite_confidence(text, score, expected):
    if expected is None:
        with pytest.raises(ValueError):
            timer.parse_countdown(text, score)
    else:
        assert timer.parse_countdown(text, score) == expected


@pytest.mark.parametrize("mode,expected", [("shortest", 155), ("longest", 180)])
def test_samples_use_absolute_deadlines_and_recovery_preserves_them(context, mode, expected):
    assert run(context, "config", mode=mode)
    assert run(context, "begin")
    assert run(context, "collect", slot=1)
    context.now = 105
    context.ocr["best"]["text"] = "00:00:50"
    assert run(context, "collect", slot=2)
    context.now = 110
    assert run(context, "finalize")
    assert timer.load_state(context)["deadline"] == expected
    context.run_recognition.reset_mock()
    assert run(context, "resume") and run(context, "collect", slot=3)
    assert timer.load_state(context)["deadline"] == expected
    context.run_recognition.assert_not_called()


@pytest.mark.parametrize("failed", [False, True])
def test_missing_or_unreadable_visible_timers_use_fixed_fallback(context, failed):
    assert run(context, "config", mode="shortest", seconds=10)
    assert run(context, "begin")
    if failed:
        context.ocr["best"]["text"] = "?"
        assert run(context, "collect", slot=1)
    context.now = 150
    assert run(context, "finalize")
    state = timer.load_state(context)
    assert state["fallback"] and state["deadline"] == 160


@pytest.mark.parametrize("changed,expected", [
    (None, "CommonRecoveryFrozenEnter"),
    ({"FurnitureEnhance_PageGuard", "FurnitureEnhance_ReadyPreview"}, "FurnitureTimer_Resume"),
    ({"CommonLoadingInterrupt"}, "CommonRecoveryEnter"),
    ({"CommonNetworkInterrupt"}, "CommonRecoveryEnter"),
])
def test_freeze_is_revalidated_against_a_fresh_page(context, changed, expected):
    assert run(context, "begin") and run(context, "collect", slot=1)
    context.hits = {"FurnitureEnhance_PageGuard", "FurnitureEnhance_BusyPreview",
                    "FurnitureEnhance_SelectedBusy1"}
    context.frozen, context.after_freeze = True, changed
    assert run(context, "wait")
    assert context.anchors[timer.NEXT_ANCHOR] == expected
    assert context.wait_freezes.call_args.kwargs["wait_freezes_param"].time == 30000


@pytest.mark.parametrize("stopped", [False, True])
def test_static_idle_wait_is_cancellable_without_freeze_or_restart(context, stopped, monkeypatch):
    assert run(context, "config", seconds=10) and run(context, "begin")
    assert run(context, "finalize")
    if stopped:
        monkeypatch.setattr(timer.time, "sleep", lambda seconds: setattr(context.tasker, "stopping", True))
    assert run(context, "wait") is not stopped
    context.wait_freezes.assert_not_called()
    assert context.anchors[timer.NEXT_ANCHOR] == ("FurnitureTimer_Wait" if stopped else "FurnitureTimer_Done")


@pytest.mark.parametrize("params", [{"mode": "bad"}, {"seconds": 9}, {"seconds": True}, {"extra": 1}])
def test_invalid_config_fails_closed(context, params):
    assert run(context, "config", **params) is False


def test_interrupted_sampling_keeps_original_deadline(context):
    assert run(context, "config", mode="shortest") and run(context, "begin")
    deadline = timer.load_state(context)["deadline"]
    context.now += 20
    assert run(context, "interval", seconds=90)
    assert run(context, "resume") and run(context, "collect", slot=1)
    state = timer.load_state(context)
    assert state["deadline"] == deadline and state["fallback"] is True
    assert state["mode"] == "shortest" and state["seconds"] == 90


@pytest.mark.parametrize("factor,expected", [(1, True), (0.5, False)])
def test_busy_preview_needs_current_bright_selection(native, soleil_image, factor, expected):
    image = (soleil_image("active_timer") * factor).astype(np.uint8)
    assert native.match("FurnitureEnhance_BusyPreview", image) is expected
    assert native.match("FurnitureEnhance_SelectedBusy1", image) is expected


def test_native_state_is_per_job_not_shared_resource(native):
    states = []

    class Inspect(CustomAction):
        def run(self, context, argv):
            states.append(timer.load_state(context))
            return True

    timer.register_furniture_timer(native.resource)
    assert native.resource.register_custom_action("InspectTimer", Inspect())
    overrides = {
        "TestConfig": {"recognition": "DirectHit", "action": "Custom", "post_delay": 0,
                       "custom_action": "FurnitureTimerControl",
                       "custom_action_param": {"op": "config", "mode": "longest"}, "next": ["TestInspect"]},
        "TestInspect": {"recognition": "DirectHit", "action": "Custom", "post_delay": 0,
                        "custom_action": "InspectTimer", "next": []},
    }
    native.run("TestConfig", overrides)
    native.run("TestInspect", overrides)
    assert [state["mode"] for state in states] == ["longest", "fixed"]


@pytest.mark.parametrize("sample,expected", [("active_timer", 478), ("countdown_10_59", 659)])
def test_native_ocr_reads_observed_countdowns(native, soleil_image, frame, pipelines, sample, expected):
    from maa.pipeline import JOCR

    root = Path(__file__).resolve().parents[1]
    if not all((root / "assets/resource/model/ocr" / name).is_file()
               for name in ("det.onnx", "rec.onnx", "keys.txt")):
        pytest.skip("Native OCR models are not provisioned")
    image = soleil_image("active_timer")
    if sample != "active_timer":
        alternate = frame("furniture_timer", sample, {"timer": (520, 1000, 125, 65)})
        image[1000:1065, 520:645] = alternate[1000:1065, 520:645]
    params = {key: value for key, value in pipelines["FurnitureTimer_OCR"].items() if key != "recognition"}
    job = native.tasker.post_recognition("OCR", JOCR(**params), image).wait()
    assert job.succeeded
    result = job.get().nodes[0].recognition
    assert result.hit is True
    best = result.raw_detail["best"]
    assert timer.parse_countdown(best["text"], best["score"]) == expected
