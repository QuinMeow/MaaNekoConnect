"""Confirm bathroom collection with native matches and the visible daily quota."""

import json
import math
import re

import numpy as np
from maa.custom_recognition import CustomRecognition


STATE = "Soleil_BathState"


def _score(value):
    return type(value) in (int, float) and math.isfinite(value) and 0.95 <= value <= 1


def _amount(value):
    return type(value) is int and 0 <= value < 10 ** 12


def _box(box):
    box = list(box)
    if (len(box) != 4 or any(type(value) is not int for value in box)
            or not (150 <= box[0] < 600 and 300 <= box[1] < 650
                    and 12 <= box[2] <= 40 and 16 <= box[3] <= 50)
            or box[0] + box[2] > 600 or box[1] + box[3] > 650):
        raise ValueError("Bathroom marker is outside the bathtub")
    return box


def _near(first, second):
    return (abs(first[0] + first[2] / 2 - second[0] - second[2] / 2) < 40
            and abs(first[1] + first[3] / 2 - second[1] - second[3] / 2) < 60)


def _load(context):
    node = context.get_node_data(STATE)
    recognition = node.get("recognition") if isinstance(node, dict) else None
    params = recognition.get("param", {}) if isinstance(recognition, dict) else node or {}
    raw = params.get("custom_recognition_param")
    state = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(state, dict) or set(state) != {"baseline", "history", "pending", "duck_rewards"}:
        raise ValueError("Invalid bathroom state")
    baseline, history, pending = state["baseline"], state["history"], state["pending"]
    if baseline is not None and (type(baseline) is not int or not 0 <= baseline <= 2):
        raise ValueError("Invalid bathroom quota baseline")
    if not isinstance(history, list) or len(history) > (baseline or 0):
        raise ValueError("Invalid bathroom attempt budget")
    for index, box in enumerate(history):
        _box(box)
        if any(_near(box, old) for old in history[:index]):
            raise ValueError("Repeated bathroom target")
    if pending is not None and (
            not isinstance(pending, dict) or set(pending) != {"quota", "box", "ducks_before"}
            or type(pending["quota"]) is not int or not history
            or pending["quota"] != baseline - len(history) + 1 or pending["box"] != history[-1]
            or (pending["ducks_before"] is not None and not _amount(pending["ducks_before"]))):
        raise ValueError("Invalid pending bathroom click")
    rewards = state["duck_rewards"]
    if (not isinstance(rewards, list) or len(rewards) != len(history) - (pending is not None)
            or any(value is not None and (type(value) is not int or not 1 <= value <= 10) for value in rewards)):
        raise ValueError("Invalid confirmed duck rewards")
    return state


def _save(context, state):
    if context.override_pipeline({STATE: {
            "recognition": "Custom", "custom_recognition": "SoleilBathArrow",
            "custom_recognition_param": state}}) is not True:
        raise RuntimeError("Could not persist bathroom budget")


def _quota(context, image):
    label = context.run_recognition("Soleil_BathQuotaLabel", image)
    if label is None or label.hit is not True or label.best_result is None:
        raise ValueError("Missing bathroom quota label")
    best = label.best_result
    x, y, width, height = best.box
    if (not _score(best.score) or not (150 <= x < 600 and 180 <= y < 600)
            or not 70 <= width <= 150 or not 14 <= height <= 35):
        raise ValueError("Uncertain bathroom quota label")
    scale = width / 140
    roi = [x + round(188 * scale), y - round(2 * scale), round(35 * scale), round(36 * scale)]
    name = "Soleil_BathQuota"
    quota = context.run_recognition(name, image, {name: {"roi": roi}})
    if quota is None or quota.hit is not True or quota.best_result is None:
        raise ValueError("Missing bathroom quota")
    best = quota.best_result
    if not _score(best.score) or not isinstance(best.text, str) or re.fullmatch("[0-2]", best.text) is None:
        raise ValueError("Uncertain bathroom quota")
    return int(best.text)


def _markers(context, image):
    detail = context.run_recognition("Soleil_BathMarkers", image)
    if detail is None or type(detail.hit) is not bool:
        raise ValueError("Missing native bathroom marker result")
    if not detail.hit:
        return []
    items = detail.filtered_results or [item for item in detail.all_results if _score(item.score)]
    if not items:
        raise ValueError("Native bathroom match has no targets")
    boxes = []
    for item in sorted(items, key=lambda match: match.score, reverse=True):
        if not _score(item.score):
            raise ValueError("Uncertain bathroom marker")
        box = _box(item.box)
        if not any(_near(box, old) for old in boxes):
            boxes.append(box)
    if len(boxes) > 2:
        raise ValueError("More than two bathroom markers")
    return sorted(boxes, key=lambda box: (box[1], box[0]))


def _read_ducks(context, image):
    try:
        icon = context.run_recognition("Soleil_BathDuckIcon", image)
        if icon is None or icon.hit is not True or icon.best_result is None or not _score(icon.best_result.score):
            return None
        detail = context.run_recognition("Soleil_BathDuckCount", image)
        if detail is None or detail.hit is not True or len(detail.filtered_results or []) != 1:
            return None
        best = detail.best_result
        if (best is None or not _score(best.score) or not isinstance(best.text, str)
                or re.fullmatch(r"(?:0|[1-9][0-9]{0,11}|[1-9][0-9]{0,2}(?:,[0-9]{3}){1,3})", best.text) is None):
            return None
        value = int(best.text.replace(",", ""))
        return value if _amount(value) else None
    except Exception:
        return None


def _confirm(context, state, quota, boxes, image, allow_unknown):
    pending = state["pending"]
    if (pending is None or quota != pending["quota"] - 1
            or any(_near(pending["box"], box) for box in boxes)):
        return None
    before, after = pending["ducks_before"], _read_ducks(context, image)
    delta = after - before if before is not None and after is not None else None
    if delta is None or not 1 <= delta <= 10:
        if not allow_unknown:
            return None
        delta = None
    rewards = state["duck_rewards"] + [delta]
    known = [value for value in rewards if value is not None]
    unknown = len(rewards) - len(known)
    reward = f"鸭子 +{delta}（余额 {before} → {after}）" if delta is not None else "鸭子增量未确认"
    total = f"累计 +{sum(known)}" if not unknown else (
        f"已确认累计 +{sum(known)}，另{unknown}次未确认" if known else "累计增量未确认")
    message = f"浴室：已领取1名，{reward}；{total}，剩余 {quota} 次"
    if context.tasker.stopping or context.override_pipeline({"Soleil_BathLog": {
            "focus": {"Node.Action.Succeeded": message}}}) is not True:
        raise RuntimeError("Could not prepare bathroom reward log")
    _save(context, {**state, "pending": None, "duck_rewards": rewards})
    print(message, flush=True)
    return {"quota": quota, "ducks": delta, "confirmed_ducks": sum(known), "unknown_rewards": unknown}


class SoleilBathArrow(CustomRecognition):
    def analyze(self, context, argv):
        try:
            params = json.loads(argv.custom_recognition_param)
            if (not isinstance(params, dict) or set(params) != {"op"}
                    or params["op"] not in ("reset", "target", "done", "confirm", "confirm_unknown") or context.tasker.stopping
                    or not isinstance(argv.image, np.ndarray) or argv.image.shape != (1280, 720, 3)
                    or argv.image.dtype != np.uint8):
                return None
            page = context.run_recognition("Soleil_BathPage", argv.image)
            if page is None or page.hit is not True or context.tasker.stopping:
                return None
            state, quota, op = _load(context), _quota(context, argv.image), params["op"]
            if op == "reset":
                if state["baseline"] is not None or state["history"] or state["pending"] is not None:
                    return None
                state["baseline"] = quota
                _save(context, state)
                print(f"浴室：剩余入浴 {quota} 次", flush=True)
                return self.AnalyzeResult(box=argv.roi, detail={"quota": quota})
            if state["baseline"] is None:
                return None
            boxes = _markers(context, argv.image)
            if op in ("confirm", "confirm_unknown"):
                detail = _confirm(context, state, quota, boxes, argv.image, op == "confirm_unknown")
                return self.AnalyzeResult(box=argv.roi, detail=detail) if detail is not None else None
            if (state["pending"] is not None or context.tasker.stopping
                    or quota != state["baseline"] - len(state["history"])):
                return None
            if op == "done":
                if quota == 0 and not boxes:
                    return self.AnalyzeResult(box=argv.roi, detail={"collected": len(state["history"]), "quota": 0})
                return None
            if quota == 0 or len(state["history"]) >= 2:
                return None
            box = next((box for box in boxes if not any(_near(box, old) for old in state["history"])), None)
            if box is None:
                return None
            history = state["history"] + [box]
            pending = {"quota": quota, "box": box, "ducks_before": _read_ducks(context, argv.image)}
            _save(context, {**state, "history": history, "pending": pending})
            if context.tasker.stopping:
                return None
            return self.AnalyzeResult(box=box, detail={"attempt": len(history), "quota": quota})
        except Exception:
            return None


def register_soleil(registry):
    if registry.register_custom_recognition("SoleilBathArrow", SoleilBathArrow()) is not True:
        raise RuntimeError("Failed to register SoleilBathArrow")
