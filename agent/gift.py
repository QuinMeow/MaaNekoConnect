"""Bound both gift tabs by configured goals and confirmed native quota changes."""

import json
import math
import re

from maa.custom_action import CustomAction


STATE_NODE = "DailyGift_State"


def new_budget(left=3, right=3):
    if any(type(value) is not int or not 0 <= value <= 3 for value in (left, right)):
        raise ValueError("Gift counts must be integers from zero to three")
    return {"goals": [left, right], "done": [0, 0], "side": -1,
            "quota": None, "pending": False, "ready": False, "searches": 0}


def advance_quota(state, quota):
    if type(quota) is not int or not 0 <= quota <= 3 or state["side"] not in (0, 1):
        raise ValueError("Unknown gift quota or tab")
    if state["pending"]:
        if type(state["quota"]) is not int or quota != state["quota"] - 1:
            raise ValueError("Gift quota must decrease by exactly one after a result")
        state["done"][state["side"]] += 1
        state["pending"] = False
    elif state["quota"] is not None and quota != state["quota"]:
        raise ValueError("Gift quota changed without a confirmed challenge")
    state["quota"] = quota
    state["ready"] = quota > 0 and state["done"][state["side"]] < state["goals"][state["side"]]
    return state["ready"]


def _load(context):
    node = context.get_node_data(STATE_NODE)
    action = node.get("action") if isinstance(node, dict) else None
    params = action.get("param", {}) if isinstance(action, dict) else node or {}
    raw = params.get("custom_action_param", {})
    state = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(state, dict) or set(state) != set(new_budget()):
        raise ValueError("Invalid gift budget state")
    new_budget(*state["goals"])
    if (state["side"] not in (-1, 0, 1) or type(state["pending"]) is not bool
            or type(state["ready"]) is not bool or len(state["done"]) != 2
            or any(type(count) is not int or not 0 <= count <= 3 for count in state["done"])
            or type(state["searches"]) is not int or not 0 <= state["searches"] <= 8):
        raise ValueError("Invalid gift progress")
    return state


def _save(context, state):
    if context.override_pipeline({STATE_NODE: {"action": "Custom", "custom_action": "DailyGiftControl",
                                              "custom_action_param": state}}) is not True:
        raise RuntimeError("Could not persist gift budget")


def _route(context, node):
    return context.set_anchor("DailyGift_Next", node) is True


def _next_tab(context, state):
    side = state["side"] + 1
    while side < 2 and state["goals"][side] == 0:
        side += 1
    state.update(ready=False, quota=None)
    if side == 2:
        _save(context, state)
        return _route(context, "DailyGift_ResultHome")
    state["side"] = side
    _save(context, state)
    return _route(context, "DailyGift_SelectLeft" if side == 0 else "DailyGift_SelectRight")


def _read_quota(context, state):
    image = context.tasker.controller.cached_image
    tab = "DailyGift_LeftTab" if state["side"] == 0 else "DailyGift_RightTab"
    matched = context.run_recognition(tab, image)
    quota = context.run_recognition("DailyGift_QuotaOCR", image)
    if matched is None or matched.hit is not True or quota is None or quota.hit is not True:
        raise ValueError("Gift tab or quota was not recognized")
    best = quota.best_result
    if best is None or not math.isfinite(best.score) or not 0.95 <= best.score <= 1:
        raise ValueError("Uncertain gift quota")
    match = re.fullmatch(r"([0-3])[/\uff0f]3", best.text)
    if match is None:
        raise ValueError("Invalid gift quota")
    return int(match[1])


class DailyGiftControl(CustomAction):
    def run(self, context, argv):
        try:
            params = json.loads(argv.custom_action_param)
            state = _load(context)
            op = params.get("op")
            if op in ("left", "right") and set(params) == {"op", "count"}:
                value = params["count"]
                if type(value) is not int or not 0 <= value <= 3 or state["side"] != -1:
                    return False
                state["goals"][0 if op == "left" else 1] = value
                _save(context, state)
                return True
            if set(params) != {"op"} or context.tasker.stopping:
                return False
            if op == "begin":
                if state["side"] != -1 or state["pending"]:
                    return False
                return _next_tab(context, state)
            if op == "list":
                quota = _read_quota(context, state)
                new_round = state["pending"] or state["quota"] is None
                ready = advance_quota(state, quota)
                if ready and new_round:
                    state["searches"] = 0
                _save(context, state)
                message = (f"礼物关卡：{'左栏' if state['side'] == 0 else '右栏'}，"
                           f"已完成 {state['done'][state['side']]}/{state['goals'][state['side']]}，免费剩余 {quota}")
                if context.override_pipeline({"DailyGift_Log": {"focus": {
                        "Node.Action.Succeeded": message}}}) is not True:
                    return False
                return _route(context, "DailyGift_ScrollBottom") if ready else _next_tab(context, state)
            if op == "search":
                if not state["ready"] or state["pending"] or state["searches"] >= 8:
                    return False
                state["searches"] += 1
                _save(context, state)
                result = context.run_action("DailyGift_SearchSwipe")
                return result is not None and result.success is True
            if op == "spend":
                if not state["ready"] or state["pending"] or state["side"] not in (0, 1):
                    return False
                if state["done"][state["side"]] >= state["goals"][state["side"]]:
                    return False
                state.update(ready=False, pending=True)
                _save(context, state)
                result = context.run_action("DailyGift_QuickClick")
                return result is not None and result.success is True
            return False
        except Exception:
            print("礼物关卡：免费次数或结果未识别，已停止", flush=True)
            return False


def register_gift(registry):
    if registry.register_custom_action("DailyGiftControl", DailyGiftControl()) is not True:
        raise RuntimeError("Failed to register DailyGiftControl")
