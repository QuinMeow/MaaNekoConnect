"""Compare native arena OCR and retain the free-refresh budget in Context."""

import json
import math
import re
from decimal import Decimal

from maa.custom_action import CustomAction


STATE_NODE = "DailyContest_State"


def parse_rating(text, score):
    if (not isinstance(text, str) or type(score) not in (int, float)
            or not math.isfinite(score) or not 0.95 <= score <= 1):
        raise ValueError("A confident opponent rating is required")
    match = re.fullmatch(r"([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)([KM]?)", text)
    if match is None:
        raise ValueError("Invalid opponent rating")
    value = Decimal(match[1].replace(",", "")) * {"": 1, "K": 1000, "M": 1000000}[match[2]]
    if value != int(value) or value < 0:
        raise ValueError("Invalid opponent rating precision")
    return int(value)


def refresh_decision(rating, threshold, remaining, previous):
    if type(remaining) is not int or not 0 <= remaining <= 3:
        raise ValueError("Unknown free refresh quota")
    if previous is not None and remaining != previous - 1:
        raise ValueError("Free refresh quota did not decrease by exactly one")
    return "refresh" if rating >= threshold and remaining > 0 else "select"


def _load(context):
    node = context.get_node_data(STATE_NODE)
    action = node.get("action") if isinstance(node, dict) else None
    params = action.get("param", {}) if isinstance(action, dict) else node or {}
    raw = params.get("custom_action_param", {})
    state = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(state, dict) or set(state) != {"position", "threshold", "previous", "quota"}:
        raise ValueError("Invalid contest state")
    if state["position"] not in ("top", "middle", "bottom"):
        raise ValueError("Invalid opponent position")
    if type(state["threshold"]) is not int or not 0 <= state["threshold"] <= 10**12:
        raise ValueError("Invalid opponent threshold")
    if any(value is not None and (type(value) is not int or not 0 <= value <= 3)
           for value in (state["previous"], state["quota"])):
        raise ValueError("Invalid free-refresh budget")
    return state


def _save(context, state):
    if context.override_pipeline({STATE_NODE: {"action": "Custom", "custom_action": "DailyContestControl",
                                              "custom_action_param": state}}) is not True:
        raise RuntimeError("Could not persist contest budget")


def _ocr(context, node):
    result = context.run_recognition(node, context.tasker.controller.cached_image)
    if result is None or result.hit is not True or result.best_result is None:
        raise ValueError("Missing contest OCR")
    best = result.best_result
    if not math.isfinite(best.score) or not 0.95 <= best.score <= 1:
        raise ValueError("Uncertain contest OCR")
    return best.text, best.score


def _free_refreshes(context):
    text, _ = _ocr(context, "DailyContest_RefreshOCR")
    match = re.fullmatch(r"\u3042\u3068([0-3])\u56de", text)
    if match is None:
        raise ValueError("Unknown free-refresh quota")
    return int(match[1])


class DailyContestControl(CustomAction):
    def run(self, context, argv):
        try:
            params = json.loads(argv.custom_action_param)
            state = _load(context)
            op = params.get("op")
            if op == "position" and set(params) == {"op", "position"}:
                if params["position"] not in ("top", "middle", "bottom"):
                    return False
                state["position"] = params["position"]
                _save(context, state)
                return True
            if op == "threshold" and set(params) == {"op", "threshold"}:
                value = params["threshold"]
                if type(value) is not int or not 0 <= value <= 10**12:
                    return False
                state["threshold"] = value
                _save(context, state)
                return True
            if set(params) != {"op"} or context.tasker.stopping:
                return False
            if op == "decide":
                route = "select"
                if state["threshold"]:
                    rating = parse_rating(*_ocr(context, "DailyContest_RatingOCR"))
                    quota = _free_refreshes(context)
                    route = refresh_decision(rating, state["threshold"], quota, state["previous"])
                    state.update(quota=quota, previous=None)
                    _save(context, state)
                    message = f"竞技场：首位评分 {rating}，阈值 {state['threshold']}，免费刷新剩余 {quota}"
                    if context.override_pipeline({"DailyContest_Log": {"focus": {
                            "Node.Action.Succeeded": message}}}) is not True:
                        return False
                target = "DailyContest_Refresh" if route == "refresh" else "Daily_ContestOpponent"
                y = {"top": 850, "middle": 965, "bottom": 1080}[state["position"]]
                if context.override_pipeline({"Daily_ContestOpponent": {"target": [365, y, 30, 20]}}) is not True:
                    return False
                return context.set_anchor("DailyContest_Next", target) is True
            if op == "refresh":
                if state["previous"] is not None or type(state["quota"]) is not int or state["quota"] <= 0:
                    return False
                if _free_refreshes(context) != state["quota"]:
                    return False
                state["previous"] = state["quota"]
                _save(context, state)
                result = context.run_action("DailyContest_RefreshClick")
                return result is not None and result.success is True
            return False
        except Exception:
            print("竞技场：评分或免费刷新次数未识别，已停止", flush=True)
            return False


def register_contest(registry):
    if registry.register_custom_action("DailyContestControl", DailyContestControl()) is not True:
        raise RuntimeError("Failed to register DailyContestControl")
