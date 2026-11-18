"""Context-local countdown data and cancellable waits; selection stays in JSON."""

import json
import math
import re
import time

import numpy as np

from maa.custom_action import CustomAction
from maa.pipeline import JWaitFreezes


STATE_NODE = "FurnitureTimer_State"
NEXT_ANCHOR = "FurnitureTimer_Next"
TIMER_FREEZE_PARAMETERS = {
    "time": 30000, "target": [520, 1000, 125, 65], "threshold": 0.000001,
    "method": 1, "rate_limit": 1000, "timeout": 35000,
}
_MODES = ("fixed", "shortest", "longest")
_PHASES = ("idle", "sampling", "resume", "waiting", "complete")


def parse_countdown(text, score):
    if (
        not isinstance(text, str)
        or re.fullmatch(r"[0-9]{2}:[0-9]{2}:[0-9]{2}", text) is None
        or type(score) not in (int, float)
        or not math.isfinite(score)
        or not 0.9 <= score <= 1
    ):
        raise ValueError("A confident strict HH:MM:SS result is required")
    hours, minutes, seconds = map(int, text.split(":"))
    if minutes >= 60 or seconds >= 60:
        raise ValueError("Invalid countdown components")
    return hours * 3600 + minutes * 60 + seconds


def _custom_params(node):
    if not isinstance(node, dict):
        return {}
    action = node.get("action")
    if isinstance(action, dict):
        raw = action.get("param", {}).get("custom_action_param", {})
    else:
        raw = node.get("custom_action_param", {})
    return json.loads(raw) if isinstance(raw, str) else raw


def load_state(context):
    state = {
        "op": "state", "mode": "fixed", "seconds": 60, "phase": "idle",
        "deadline": None, "samples": [], "failed": False, "fallback": False,
        "fallback_reason": "", "selected_slot": 0,
    }
    raw = _custom_params(context.get_node_data(STATE_NODE))
    if not isinstance(raw, dict):
        raise ValueError("Invalid context-local timer state")
    if raw.keys() - state.keys():
        raise ValueError("Unknown timer-state field")
    state.update(raw)
    if state["op"] != "state":
        raise ValueError("Invalid timer state marker")
    if state["mode"] not in _MODES or state["phase"] not in _PHASES:
        raise ValueError("Invalid timer mode or phase")
    if type(state["seconds"]) is not int or not 10 <= state["seconds"] <= 86400:
        raise ValueError("Interval must be 10..86400 seconds")
    if type(state["selected_slot"]) is not int or not 0 <= state["selected_slot"] <= 5:
        raise ValueError("Invalid selected timer slot")
    deadline = state["deadline"]
    if deadline is not None and (
        type(deadline) not in (int, float) or not math.isfinite(deadline) or deadline < 0
    ):
        raise ValueError("Invalid timer deadline")
    samples = state["samples"]
    if (
        not isinstance(samples, list) or len(samples) > 5
        or any(type(item) not in (int, float) or not math.isfinite(item) or item < 0 for item in samples)
        or type(state["failed"]) is not bool or type(state["fallback"]) is not bool
        or not isinstance(state["fallback_reason"], str)
    ):
        raise ValueError("Invalid timer sample data")
    return state


def _save(context, state):
    if context.override_pipeline({STATE_NODE: {
        "action": "Custom", "custom_action": "FurnitureTimerControl",
        "custom_action_param": state,
    }}) is not True:
        raise RuntimeError("Could not persist context-local timer state")


def _route(context, node):
    if context.set_anchor(NEXT_ANCHOR, node) is not True:
        raise RuntimeError("Could not set timer continuation")
    return True


def _checkpoint(context):
    if context.set_anchor("CommonRecoveryResume", "FurnitureTimer_Resume") is not True:
        raise RuntimeError("Could not set timer recovery checkpoint")


def _hit(context, node, image):
    result = context.run_recognition(node, image)
    return result is not None and result.hit is True


def _capture(context):
    if context.tasker.stopping:
        return None
    capture = context.tasker.controller.post_screencap().wait()
    if capture.succeeded is not True or context.tasker.stopping:
        return None
    image = context.tasker.controller.cached_image
    if not isinstance(image, np.ndarray) or image.ndim != 3 or image.size == 0:
        return None
    return image


def _interrupted(context, image):
    return (
        _hit(context, "CommonNetworkInterrupt", image)
        or _hit(context, "CommonLoadingInterrupt", image)
    )


def _wait(context, state):
    if state["phase"] != "waiting" or state["deadline"] is None:
        raise ValueError("Timer must have a committed deadline before waiting")
    while not context.tasker.stopping:
        image = _capture(context)
        if image is None:
            return False
        if _interrupted(context, image) or not _hit(context, "FurnitureEnhance_PageGuard", image):
            return _route(context, "CommonRecoveryEnter")
        remaining = state["deadline"] - time.monotonic()
        if remaining <= 0:
            state["phase"] = "complete"
            _save(context, state)
            return _route(context, "FurnitureTimer_Done")

        slot = state["selected_slot"]
        busy = (
            slot > 0
            and _hit(context, "FurnitureEnhance_BusyPreview", image)
            and _hit(context, f"FurnitureEnhance_SelectedBusy{slot}", image)
        )
        if not busy:
            unidentified_busy = slot == 0 and _hit(context, "FurnitureEnhance_BusyPreview", image)
            ready = _hit(context, "FurnitureEnhance_ReadyPreview", image)
            if ready and slot > 0:
                # Selection stays in JSON; resume only changes the monitored item.
                return _route(context, "FurnitureTimer_Resume")
            if not unidentified_busy and not ready:
                return _route(context, "CommonRecoveryEnter")
            time.sleep(min(1.0, remaining))
            continue
        if remaining < 30:
            time.sleep(min(1.0, remaining))
            continue

        # One continuous native window preserves the thirty-second freeze proof.
        params = JWaitFreezes(**{
            **TIMER_FREEZE_PARAMETERS,
            "target": list(TIMER_FREEZE_PARAMETERS["target"]),
            "timeout": min(TIMER_FREEZE_PARAMETERS["timeout"], int(remaining * 1000)),
        })
        frozen = context.wait_freezes(wait_freezes_param=params)
        if context.tasker.stopping:
            return False
        image = _capture(context)
        if image is None:
            return False
        if _interrupted(context, image) or not _hit(context, "FurnitureEnhance_PageGuard", image):
            return _route(context, "CommonRecoveryEnter")
        if time.monotonic() >= state["deadline"]:
            state["phase"] = "complete"
            _save(context, state)
            return _route(context, "FurnitureTimer_Done")
        if frozen is True:
            if _hit(context, "FurnitureEnhance_ReadyPreview", image):
                state["selected_slot"] = 0
                _save(context, state)
                return _route(context, "FurnitureTimer_Resume")
            if (
                _hit(context, "FurnitureEnhance_BusyPreview", image)
                and _hit(context, f"FurnitureEnhance_SelectedBusy{slot}", image)
            ):
                return _route(context, "CommonRecoveryFrozenEnter")
            return _route(context, "CommonRecoveryEnter")
    return False


class FurnitureTimerControl(CustomAction):
    def run(self, context, argv):
        try:
            params = json.loads(argv.custom_action_param)
            if not isinstance(params, dict) or params.keys() - {"op", "mode", "seconds", "slot"}:
                return False
            op = params.get("op")
            state = load_state(context)
            if op == "config":
                if params.keys() - {"op", "mode", "seconds"}:
                    return False
                mode = params.get("mode", "fixed")
                seconds = params.get("seconds", state["seconds"])
                if mode not in _MODES or type(seconds) is not int or not 10 <= seconds <= 86400:
                    return False
                state.update(mode=mode, seconds=seconds)
                _save(context, state)
                return True
            if op == "interval":
                if params.keys() != {"op", "seconds"}:
                    return False
                seconds = params["seconds"]
                if type(seconds) is not int or not 10 <= seconds <= 86400:
                    return False
                state["seconds"] = seconds
                _save(context, state)
                return True
            if params.keys() - ({"op", "slot"} if op == "collect" else {"op"}):
                return False
            if op in ("begin", "resume"):
                _checkpoint(context)
                if op == "resume" or state["phase"] in ("sampling", "resume", "waiting"):
                    if state["deadline"] is None:
                        return False
                    if state["phase"] == "sampling" and state["mode"] != "fixed":
                        state.update(failed=True, fallback=True, fallback_reason="sampling_interrupted")
                    state["phase"] = "resume"
                    state["selected_slot"] = 0
                else:
                    state.update(
                        phase="sampling", deadline=time.monotonic() + state["seconds"],
                        samples=[], failed=False, fallback=False, fallback_reason="",
                        selected_slot=0,
                    )
                _save(context, state)
                return _route(context, "FurnitureTimer_Sample")
            if op == "collect":
                slot = params.get("slot")
                if type(slot) is not int or not 1 <= slot <= 5:
                    return False
                if state["phase"] not in ("sampling", "resume", "waiting"):
                    return False
                state["selected_slot"] = slot
                if state["phase"] != "sampling" or state["mode"] == "fixed":
                    if state["phase"] == "sampling":
                        state["deadline"] = time.monotonic() + state["seconds"]
                    state["phase"] = "waiting"
                    _save(context, state)
                    return _route(context, "FurnitureTimer_Wait")
                sampled_at = time.monotonic()
                try:
                    result = context.run_recognition(
                        "FurnitureTimer_OCR", context.tasker.controller.cached_image
                    )
                    if result is None or result.hit is not True:
                        raise ValueError("OCR did not match")
                    best = result.raw_detail["best"]
                    seconds = parse_countdown(best["text"], best["score"])
                    state["samples"].append(sampled_at + seconds)
                except Exception:
                    state["failed"] = True
                    state["fallback_reason"] = "countdown_read_failed"
                _save(context, state)
                target = "FurnitureTimer_Finalize" if state["failed"] else f"FurnitureTimer_Continue{slot}"
                return _route(context, target)
            if op == "missing":
                state["failed"] = True
                state["fallback_reason"] = "preview_changed_while_sampling"
                _save(context, state)
                return _route(context, "FurnitureTimer_Finalize")
            if op == "finalize":
                if state["phase"] == "sampling":
                    samples = state["samples"]
                    if state["mode"] != "fixed" and samples and not state["failed"]:
                        target = min(samples) if state["mode"] == "shortest" else max(samples)
                        state["deadline"] = max(time.monotonic() + 10, target)
                    else:
                        state["deadline"] = time.monotonic() + state["seconds"]
                        state["fallback"] = state["mode"] != "fixed"
                        if state["fallback"] and not state["fallback_reason"]:
                            state["fallback_reason"] = "no_visible_busy_furniture"
                elif state["phase"] not in ("resume", "waiting"):
                    return False
                state["phase"] = "waiting"
                _save(context, state)
                return _route(context, "FurnitureTimer_Wait")
            if op == "wait":
                _checkpoint(context)
                return _wait(context, state)
            return False
        except Exception:
            return False


def register_furniture_timer(registry):
    if registry.register_custom_action("FurnitureTimerControl", FurnitureTimerControl()) is not True:
        raise RuntimeError("Failed to register FurnitureTimerControl")
