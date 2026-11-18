"""Context-local exchange slot and free-refresh permits; UI actions stay in JSON."""

import json
import re

from maa.custom_action import CustomAction


STATE_NODE = "DailyExchange_State"
SLOTS = ([150, 300, 195, 45], [485, 300, 195, 45],
         [150, 500, 195, 45], [485, 500, 195, 45])


def _state(context):
    node = context.get_node_data(STATE_NODE)
    if not isinstance(node, dict):
        raise ValueError("Missing exchange budget")
    action = node.get("action")
    raw = (action.get("param", {}).get("custom_action_param")
           if isinstance(action, dict) else node.get("custom_action_param"))
    raw = json.loads(raw) if isinstance(raw, str) else raw
    if (not isinstance(raw, dict) or set(raw) != {"mode", "slot", "refreshes", "expected"}
            or raw["mode"] not in ("one", "page", "free_pages")
            or type(raw["slot"]) is not int or not 0 <= raw["slot"] <= 4
            or type(raw["refreshes"]) is not int or not 0 <= raw["refreshes"] <= 5
            or (raw["expected"] is not None and
                (type(raw["expected"]) is not int or not 0 <= raw["expected"] < 5))):
        raise ValueError("Invalid exchange budget")
    return raw.copy()


def _save(context, state):
    if context.override_pipeline({STATE_NODE: {"action": "Custom", "custom_action": "ExchangeControl",
                                             "custom_action_param": state}}) is not True:
        raise RuntimeError("Cannot save exchange permits")


def _route(context, target):
    return context.set_anchor("DailyExchange_Next", target) is True


def _capture(context):
    controller = context.tasker.controller
    if context.tasker.stopping or controller.post_screencap().wait().succeeded is not True:
        raise RuntimeError("Cannot capture exchange page")
    if context.tasker.stopping:
        raise RuntimeError("Exchange cancelled")
    image = controller.cached_image
    result = context.run_recognition("DailyExchange_PageGuard", image)
    if result is None or result.hit is not True:
        raise ValueError("Exchange page is not positively identified")
    return image


def _remaining(context, image):
    result = context.run_recognition("DailyExchange_FreeCount", image)
    if result is None or result.hit is not True:
        raise ValueError("Missing free refresh count")
    best = result.raw_detail["best"]
    text, score = best["text"], best["score"]
    if (not isinstance(text, str) or re.fullmatch(r"[0-5]/5", text) is None
            or type(score) not in (int, float) or not .95 <= score <= 1):
        raise ValueError("Invalid free refresh count")
    return int(text[0])


def _offer(context, slot):
    x, y, _, _ = SLOTS[slot]
    guard = ["DailyExchange_PageGuard", {
        "recognition": "TemplateMatch", "template": ["daily/exchange_offer.png", "daily/exchange_offer_lower.png"],
        "roi": SLOTS[slot], "threshold": .97,
    }, {
        "recognition": "TemplateMatch", "template": ["daily/exchange_gold_marker.png",
                                                      "daily/exchange_gold_marker_lower.png"],
        "roi": [x + 24, y - 40, 40, 36], "threshold": .97,
    }]
    if context.override_pipeline({"Daily_GoldOffer": {
            "recognition": "And", "all_of": guard, "box_index": 1}}) is not True:
        raise RuntimeError("Cannot select exchange slot")


class ExchangeControl(CustomAction):
    def run(self, context, argv):
        try:
            params = json.loads(argv.custom_action_param)
            if not isinstance(params, dict) or context.tasker.stopping:
                return False
            state = _state(context)
            op = params.get("op")
            if op == "config":
                if (set(params) != {"op", "mode"} or params["mode"] not in ("one", "page", "free_pages")
                        or state["slot"] or state["refreshes"] or state["expected"] is not None):
                    return False
                state["mode"] = params["mode"]
                _save(context, state)
                return True
            if set(params) != {"op"}:
                return False
            image = _capture(context)
            if op == "verify":
                if state["expected"] is None or _remaining(context, image) != state["expected"]:
                    return False
                state.update(slot=0, expected=None)
                _save(context, state)
                return _route(context, "DailyExchange_Select")
            if op != "next" or state["expected"] is not None:
                return False
            if state["mode"] == "one" and state["slot"]:
                return _route(context, "Daily_Return")
            while state["slot"] < 4:
                _offer(context, state["slot"])
                result = context.run_recognition("Daily_GoldOffer", image)
                # Commit the slot before opening its preview; recovery cannot repeat it.
                state["slot"] += 1
                _save(context, state)
                if result is not None and result.hit is True:
                    return _route(context, "Daily_GoldOffer")
            if state["mode"] != "free_pages":
                return _route(context, "Daily_Return")
            remaining = _remaining(context, image)
            if remaining == 0:
                return _route(context, "Daily_Return")
            if state["refreshes"] >= 5:
                return False
            state.update(expected=remaining - 1, refreshes=state["refreshes"] + 1)
            _save(context, state)
            return _route(context, "DailyExchange_RefreshOpen")
        except Exception:
            return False


def register_exchange(registry):
    if registry.register_custom_action("ExchangeControl", ExchangeControl()) is not True:
        raise RuntimeError("Failed to register ExchangeControl")
