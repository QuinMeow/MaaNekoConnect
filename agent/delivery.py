"""Fail-closed delivery-map state aggregation using native recognitions only."""

import json
import math
import re

import numpy as np
from maa.custom_recognition import CustomRecognition


STATE_NODE = "DailyDelivery_State"
_PREFIX = "DailyDelivery_"


def _score(value, minimum=0.95):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= 1


def parse_order_count(text, score):
    match = re.fullmatch(r"(?:\u4f9d\u983c\u6570[:\uff1a])?([0-9]|1[0-8])[/\uff0f]18\u4ef6", text) if isinstance(text, str) else None
    if match is None or not _score(score):
        raise ValueError("A confident complete order counter from 0/18 to 18/18 is required")
    return int(match[1])


def _hit(detail):
    if detail is None or type(detail.hit) is not bool:
        raise ValueError("Native recognition did not return a boolean result")
    return detail.hit


def _ocr(detail):
    if not _hit(detail):
        raise ValueError("Native OCR did not match")
    best = detail.best_result
    if best is None or not isinstance(best.text, str) or not _score(best.score):
        raise ValueError("Native OCR has no confident best result")
    return best.text, best.score


def _state(context):
    node = context.get_node_data(STATE_NODE)
    if not isinstance(node, dict):
        raise ValueError("Context-local delivery state is missing")
    recognition = node.get("recognition")
    params = recognition.get("param", {}) if isinstance(recognition, dict) else node
    raw = params.get("custom_recognition_param")
    raw = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(raw, dict) or set(raw) != {"selected"}:
        raise ValueError("Invalid delivery state")
    point = raw["selected"]
    if point is not None and (
        not isinstance(point, list) or len(point) != 2
        or any(type(value) is not int for value in point)
        or not 0 <= point[0] < 720 or not 0 <= point[1] < 1280
    ):
        raise ValueError("Invalid selected pin center")
    return point


def _save(context, point):
    if context.override_pipeline({STATE_NODE: {
        "recognition": "Custom", "custom_recognition": "DailyDeliveryMapProbe",
        "custom_recognition_param": {"selected": point},
    }}) is not True:
        raise RuntimeError("Could not commit context-local delivery selection")


def _center(box):
    return box[0] + box[2] // 2, box[1] + box[3] // 2


def _near(first, second):
    return sum((a - b) ** 2 for a, b in zip(first, second)) <= 20 ** 2


def _pins(context, detail):
    if not _hit(detail):
        return []
    items = detail.filtered_results
    if not items:
        node = context.get_node_data(_PREFIX + "Pins")
        recognition = node.get("recognition") if isinstance(node, dict) else None
        params = recognition.get("param", {}) if isinstance(recognition, dict) else node or {}
        threshold = params.get("threshold", 0.95)
        threshold = min(threshold) if isinstance(threshold, list) and threshold else threshold
        if not _score(threshold, 0):
            raise ValueError("Invalid native pin threshold")
        items = [item for item in detail.all_results if _score(item.score, threshold)]
    if not items:
        raise ValueError("Native pin match has no valid target rectangles")
    boxes = []
    for item in sorted(items, key=lambda value: value.score, reverse=True):
        box = tuple(item.box)
        if (len(box) != 4 or any(type(value) is not int for value in box)
                or not _score(item.score, 0) or min(box[:2]) < 0
                or min(box[2:]) <= 0 or box[0] + box[2] > 720 or box[1] + box[3] > 1280):
            raise ValueError("Invalid native pin rectangle")
        if not any(_near(_center(box), _center(other)) for other in boxes):
            boxes.append(box)
    return sorted(boxes, key=lambda box: (_center(box)[1], _center(box)[0]))


def _scan(context, image):
    local = context.clone()
    count = parse_order_count(*_ocr(local.run_recognition(_PREFIX + "OrderCount", image)))
    pins = _pins(context, local.run_recognition(_PREFIX + "Pins", image))
    if len(pins) != count:
        raise ValueError("Pin count differs from the native order counter")
    states = []
    for box in pins:
        if context.tasker.stopping:
            raise ValueError("Task is stopping")
        x, y = _center(box)
        left, top = max(0, x - 85), max(0, y - 100)
        roi = [left, top, min(720, x + 85) - left, min(1280, y - 55) - top]
        if min(roi[2:]) <= 0:
            raise ValueError("Pin tag is outside the image")

        def recognize(suffix):
            name = _PREFIX + suffix
            return local.run_recognition(name, image, {name: {"roi": roi}})

        tag, complete, timer = _hit(recognize("Tag")), _hit(recognize("Complete")), recognize("Timer")
        timed = _hit(timer)
        if timed:
            text, _ = _ocr(timer)
            if re.fullmatch(r"[0-9]{2}:[0-5][0-9]:[0-5][0-9]", text) is None:
                raise ValueError("Invalid native HH:MM:SS countdown")
        if complete and timed or tag and not (complete or timed):
            raise ValueError("Unknown or contradictory delivery tag")
        states.append((box, "complete" if complete else "running" if timed else "pending"))
    return states


class DailyDeliveryMapProbe(CustomRecognition):
    def analyze(self, context, argv):
        try:
            params = json.loads(argv.custom_recognition_param)
            if (not isinstance(params, dict) or set(params) != {"op"}
                    or params["op"] not in ("select", "started", "verify")
                    or not isinstance(argv.image, np.ndarray) or argv.image.shape != (1280, 720, 3)
                    or argv.image.dtype != np.uint8 or context.tasker.stopping):
                return None
            op, selected = params["op"], _state(context)
            if (op == "verify" and selected is None) or (op != "verify" and selected is not None):
                return None
            states = _scan(context, argv.image)
            if context.tasker.stopping:
                return None
            box = None
            if op == "select":
                box = next((box for box, status in states if status == "pending"), None)
                if box is not None:
                    _save(context, list(_center(box)))
            elif op == "verify":
                box = next((box for box, status in states
                            if _near(selected, _center(box)) and status != "pending"), None)
                if box is not None:
                    _save(context, None)
            elif all(status != "pending" for _, status in states):
                box = (0, 0, 1, 1)
            if box is None:
                return None
            return self.AnalyzeResult(box=box, detail={"op": op, "pins": len(states),
                                                       "states": [status for _, status in states]})
        except Exception:
            return None


def register_delivery(registry):
    if registry.register_custom_recognition("DailyDeliveryMapProbe", DailyDeliveryMapProbe()) is not True:
        raise RuntimeError("Failed to register DailyDeliveryMapProbe")
