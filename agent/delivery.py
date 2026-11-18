"""Delivery overview aggregation using native recognitions."""

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
    if not isinstance(raw, dict) or set(raw) != {"selected", "started", "refresh_seen"}:
        raise ValueError("Invalid delivery state")
    started = raw["started"]
    if not isinstance(started, list) or len(started) > 54 or any(point is None for point in started):
        raise ValueError("Invalid delivery history")
    baseline = raw["refresh_seen"]
    if baseline is not None and (not isinstance(baseline, list) or len(baseline) > 18
                                 or any(point is None for point in baseline)):
        raise ValueError("Invalid refresh baseline")
    for point in [raw["selected"], *started, *(baseline or [])]:
        if point is not None and (
            not isinstance(point, list) or len(point) != 2
            or any(type(value) is not int for value in point)
            or not 0 <= point[0] < 720 or not 0 <= point[1] < 1280
        ):
            raise ValueError("Invalid pin center")
    return raw


def _save(context, state):
    if context.override_pipeline({STATE_NODE: {
        "recognition": "Custom", "custom_recognition": "DailyDeliveryMapProbe",
        "custom_recognition_param": state,
    }}) is not True:
        raise RuntimeError("Could not commit context-local delivery selection")


def _center(box):
    return box[0] + box[2] // 2, box[1] + box[3] // 2


def _near(first, second, radius=20):
    return sum((a - b) ** 2 for a, b in zip(first, second)) <= radius ** 2


def _timer_text_roi(detail, point):
    if not _hit(detail):
        return None
    left_caps = []
    for item in detail.filtered_results:
        x, y, width, height = item.box
        if ((width, height) in ((18, 26), (22, 27))
                and 45 <= point[0] - x <= 85 and 45 <= point[1] - y <= 110):
            origin = (x, y + height - 26)
            if not any(_near(origin, old, 4) for old in left_caps):
                left_caps.append(origin)
    if len(left_caps) == 1:
        x, y = left_caps[0]
        return [x + 22, y + 2, 93, 22]
    return None


def _owned_tag(detail, point):
    if not _hit(detail):
        return False
    if not detail.filtered_results:
        return True
    for item in detail.filtered_results:
        x, y, width, height = item.box
        if (width, height) == (22, 27) and 45 <= point[0] - x <= 85 and 45 <= point[1] - y <= 110:
            return True
        if (width, height) == (18, 26) and 35 <= abs(point[0] - x) <= 85 and 45 <= point[1] - y <= 110:
            return True
        if width in (117, 137) and abs(point[0] - x - width / 2) <= 25 and 45 <= point[1] - y <= 110:
            return True
    return False


def _owned_status(item, point):
    x, y = _center(item.box)
    return abs(point[0] - x) <= 25 and 45 <= point[1] - y <= 110


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
        # Opposite half-glyph centers can be 21px apart during the size animation.
        if not any(_near(_center(box), _center(other), 24) for other in boxes):
            boxes.append(box)
    return sorted(boxes, key=lambda box: (_center(box)[1], _center(box)[0]))


def _scan(context, image, strict_timer=False):
    local = context.clone()
    counter = local.run_recognition(_PREFIX + "OrderCount", image)
    shapes = pin_image(image)
    pins = _pins(context, local.run_recognition(_PREFIX + "Pins", shapes))
    if _hit(counter):
        if len(pins) != parse_order_count(*_ocr(counter)):
            raise ValueError("Pin count differs from the native order counter")
    else:
        if not _hit(local.run_recognition(_PREFIX + "CounterOccluded", image)):
            raise ValueError("Missing order counter without a confirmed covering timer")
        markers = _pins(context, local.run_recognition(_PREFIX + "Markers", shapes))
        # Neither classifier alone can authorize a partial map or empty refresh.
        if not 1 <= len(pins) == len(markers) <= 18:
            raise ValueError("Order outlines and glyphs disagree")
        partners = []
        for pin in pins:
            x, y = _center(pin)
            matches = [i for i, marker in enumerate(markers)
                       if abs(_center(marker)[0] - x) <= 15
                       and 30 <= _center(marker)[1] - y <= 65]
            if len(matches) != 1 or matches[0] in partners:
                raise ValueError("Order outlines do not pair uniquely with glyphs")
            partners.append(matches[0])
    states, timer_rois = [], []
    for box in pins:
        if context.tasker.stopping:
            raise ValueError("Task is stopping")
        x, y = _center(box)
        def recognize(suffix, fixed_roi=None):
            name = _PREFIX + suffix
            wide = suffix == "Tag"
            margin, above, below = (100, 115, 40) if wide else (85, 100, 55)
            left, top = max(0, x - margin), max(0, y - above)
            roi = [left, top, min(720, x + margin) - left, min(1280, y - below) - top]
            if min(roi[2:]) <= 0:
                raise ValueError("Pin tag is outside the image")
            params = {"roi": roi} if fixed_roi is None else {"roi": fixed_roi, "only_rec": True}
            return local.run_recognition(name, image, {name: params})

        tag = recognize("Tag")
        timer_roi = _timer_text_roi(tag, (x, y))
        if strict_timer:
            if timer_roi is None or any(_near(timer_roi[:2], old[:2], 6) for old in timer_rois):
                raise ValueError("Each paid-refresh order needs its own readable timer")
            timer_rois.append(timer_roi)
        status = recognize("Status", timer_roi)
        label = "pending"
        owned_tag = _owned_tag(tag, (x, y))
        # A neighboring capsule can hide this timer's left edge and leading zero.
        # Associate the visible countdown with its pin, not with the other capsule.
        texts = {item.text for item in status.filtered_results
                 if _score(item.score) and _owned_status(item, (x, y))} if _hit(status) else set()
        if texts:
            if len(texts) != 1:
                raise ValueError("Ambiguous delivery status")
            text = texts.pop()
            if re.fullmatch(r"\u914d\u9054\u5b8c\u4e86[!\uff01]", text):
                label = "complete"
            elif re.fullmatch(r"[0-9]{1,2}:[0-5][0-9]:[0-5][0-9]", text):
                label = "running"
            else:
                raise ValueError("Invalid native delivery status")
        elif owned_tag:
            raise ValueError("Unreadable delivery tag")
        states.append((box, label))
    return states


def pin_image(image):
    """Keep the dark food/sweets/drive glyphs, not their five rarity backgrounds."""
    blue, green, red = (image[:, :, index].astype(np.int16) for index in range(3))
    mask = ((red >= 80) & (red <= 155) & (green >= 40) & (green <= 105)
            & (blue >= 20) & (blue <= 90) & (red - green >= 20) & (green - blue >= 5))
    # Small antialias/animation differences must not change a glyph's identity.
    padded = np.pad(mask.astype(np.uint16) * 255, 1)
    smooth = sum(padded[y:y + mask.shape[0], x:x + mask.shape[1]]
                 for y in range(3) for x in range(3)) // 9
    return np.repeat(smooth.astype(np.uint8)[:, :, None], 3, axis=2)


class DailyDeliveryMapProbe(CustomRecognition):
    def analyze(self, context, argv):
        try:
            params = json.loads(argv.custom_recognition_param)
            if (not isinstance(params, dict) or set(params) != {"op"}
                    or params["op"] not in ("select", "started", "verify", "refreshed", "paid_ready",
                                             "paid_prepare", "refresh_prepare")
                    or not isinstance(argv.image, np.ndarray) or argv.image.shape != (1280, 720, 3)
                    or argv.image.dtype != np.uint8 or context.tasker.stopping):
                return None
            op, state = params["op"], _state(context)
            selected = state["selected"]
            if (op == "verify" and selected is None) or (op != "verify" and selected is not None):
                return None
            if state["refresh_seen"] is not None and op not in ("refreshed", "paid_ready"):
                return None
            states = _scan(context, argv.image, strict_timer=op in ("paid_ready", "paid_prepare"))
            if context.tasker.stopping:
                return None
            box = None
            # Cross-frame glyph fragments use the same 24px tolerance as pin deduplication.
            known = lambda candidate: any(_near(point, _center(candidate), 24) for point in state["started"])
            if op == "select":
                box = next((box for box, status in states if status == "pending" and not known(box)), None)
                if box is not None:
                    _save(context, {**state, "selected": list(_center(box))})
            elif op == "verify":
                # Animation tolerance must not borrow a neighboring order's timer.
                nearby = [(candidate, status) for candidate, status in states
                          if _near(selected, _center(candidate), 24)]
                if len(nearby) == 1 and nearby[0][1] != "pending":
                    box = nearby[0][0]
                    _save(context, {**state, "selected": None, "started": [*state["started"], selected]})
            elif op == "refreshed" and state["refresh_seen"] is not None and any(
                status == "pending" and not any(_near(point, _center(box), 24) for point in state["refresh_seen"])
                for box, status in states
            ):
                _save(context, {"selected": None, "refresh_seen": None,
                                "started": [list(_center(box)) for box, _ in states if known(box)]})
                box = (0, 0, 1, 1)
            elif op == "started" and all(status != "pending" or known(box) for box, status in states):
                box = (0, 0, 1, 1)
            elif op in ("paid_ready", "paid_prepare") and states and all(status == "running" for _, status in states):
                if op == "paid_prepare":
                    _save(context, {"selected": None, "refresh_seen": [list(_center(box)) for box, _ in states],
                                    "started": [list(_center(box)) for box, _ in states]})
                box = (0, 0, 1, 1)
            elif op == "refresh_prepare" and all(status != "pending" or known(box) for box, status in states):
                _save(context, {"selected": None, "refresh_seen": [list(_center(box)) for box, _ in states],
                                "started": [list(_center(box)) for box, status in states if status == "running" or known(box)]})
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
