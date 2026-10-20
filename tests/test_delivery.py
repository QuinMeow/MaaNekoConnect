import json
from types import SimpleNamespace as NS

import numpy as np
import pytest

from agent import delivery


def result(hit, items=()):
    return NS(hit=hit, filtered_results=list(items), all_results=list(items),
              best_result=items[0] if items else None)


class Context:
    def __init__(self, statuses):
        self.statuses = list(statuses)
        self.boxes = [[180 + i * 180, 450, 32, 40] for i in range(len(statuses))]
        self.text, self.score = f"依頼数:{len(statuses)}/18件", 0.99
        self.state, self.calls = {"selected": None}, []
        self.tasker = NS(stopping=False)
        self.save_ok, self.only_all = True, False

    def get_node_data(self, name):
        return {"custom_recognition_param": self.state} if name == delivery.STATE_NODE else {"threshold": 0.95}

    def override_pipeline(self, patch):
        self.state = patch[delivery.STATE_NODE]["custom_recognition_param"]
        return self.save_ok

    def clone(self):
        return NS(run_recognition=self.run_recognition)

    def run_recognition(self, name, image, pipeline_override=None):
        self.calls.append((name, pipeline_override))
        if name == "DailyDelivery_Pins":
            value = result(bool(self.boxes), [NS(box=box, score=0.99) for box in self.boxes])
            if self.only_all:
                value.filtered_results = []
            return value
        if name == "DailyDelivery_OrderCount":
            return result(True, [NS(text=self.text, score=self.score)])
        roi = pipeline_override[name]["roi"]
        index = min(range(len(self.statuses)), key=lambda i: abs(self.boxes[i][0] + 16 - roi[0] - 85))
        status = self.statuses[index]
        if name == "DailyDelivery_Timer":
            return result(status in ("running", "bad_timer"),
                          [NS(text="01:02:03" if status == "running" else "1:02:03", score=0.99)])
        return result(status in {"DailyDelivery_Complete": {"complete"},
                                 "DailyDelivery_Tag": {"running", "complete", "unknown", "bad_timer"}}[name])


def probe(context, op):
    return delivery.DailyDeliveryMapProbe().analyze(context, NS(
        custom_recognition_param=json.dumps({"op": op}),
        image=np.ones((1280, 720, 3), dtype=np.uint8), roi=(0, 0, 720, 1280)))


@pytest.mark.parametrize("text,valid", [("依頼数:6/18件", True), ("依頼数：0／18件", True),
                                     ("18/18件", True), ("19/18件", False), ("6/18", False),
                                     ("余り6/18件", False), ("6/18件x", False)])
def test_order_count_requires_the_complete_strict_counter(text, valid):
    if valid:
        assert 0 <= delivery.parse_order_count(text, 0.95) <= 18
    else:
        with pytest.raises(ValueError):
            delivery.parse_order_count(text, 0.99)


def test_select_merges_native_duplicates_and_verify_consumes_the_same_selection_once():
    context = Context(["running", "complete", "pending"])
    context.boxes.append([184, 451, 32, 40])
    context.only_all = True
    selected = probe(context, "select")
    assert tuple(selected.box) == (540, 450, 32, 40)
    assert probe(context, "select") is None
    assert probe(context, "started") is None and probe(context, "verify") is None
    context.statuses[2] = "running"
    assert probe(context, "verify") is not None and context.state["selected"] is None
    assert probe(context, "verify") is None
    assert all(override is None or set(override) == {name} for name, override in context.calls)


@pytest.mark.parametrize("statuses,text,expected", [([], "0/18件", True),
    (["running", "complete"], "2/18件", True), (["pending"], "1/18件", False),
    (["unknown"], "1/18件", False), (["bad_timer"], "1/18件", False),
    (["running"], "0/18件", False), ([], "6/18件", False)])
def test_refresh_requires_a_complete_known_map_without_pending_orders(statuses, text, expected):
    context = Context(statuses)
    context.text = text
    assert (probe(context, "started") is not None) is expected


@pytest.mark.parametrize("case", ["unknown", "bad_timer", "count_mismatch", "low_score", "stopped", "save_failed"])
def test_unknown_or_incomplete_native_evidence_never_authorizes_selection(case):
    context = Context([case if case in ("unknown", "bad_timer") else "pending"])
    if case == "count_mismatch":
        context.text = "0/18件"
    context.score = 0.94 if case == "low_score" else 0.99
    context.tasker.stopping = case == "stopped"
    context.save_ok = case != "save_failed"
    assert probe(context, "select") is None


@pytest.mark.parametrize("pins", [None, result(True)])
def test_missing_or_inconsistent_native_results_never_authorize_empty_map_refresh(pins):
    context = Context([])
    original = context.run_recognition
    context.run_recognition = lambda name, image, patch=None: (
        pins if name == "DailyDelivery_Pins" else original(name, image, patch))
    assert probe(context, "started") is None


@pytest.mark.parametrize("sample,op,expected", [
    ("new", "select", ["pending"] * 6),
    ("running", "select", ["pending"] * 5 + ["running"]),
    ("completed", "started", ["complete"] * 5 + ["running"]), ("empty", "started", []),
])
def test_native_map_probe_accounts_for_every_observed_pin(native, frame, sample, op, expected):
    from pathlib import Path

    if not (Path(__file__).resolve().parents[1] / "assets/resource/model/ocr/rec.onnx").is_file():
        pytest.skip("Native OCR models are not provisioned")
    observed = []

    class Observe(delivery.DailyDeliveryMapProbe):
        def analyze(self, context, argv):
            value = super().analyze(context, argv)
            observed.append(value)
            if value is not None and op == "select":
                assert delivery._state(context) == list(delivery._center(value.box))
                assert super().analyze(context, argv) is None
            return value

    assert native.resource.register_custom_recognition("DailyDeliveryMapProbe", Observe())
    image = frame("delivery", sample, {"title": (35, 25, 190, 60),
                      "count": (530, 102, 180, 38), "map": (0, 100, 710, 900),
                      "footer": (270, 1195, 180, 80)})
    matched = native.match("DailyDelivery_Select" if op == "select" else "DailyDelivery_AllStarted", image)
    assert matched is (expected is not None)
    if expected is not None:
        assert sorted(observed[-1].detail["states"]) == sorted(expected)
        assert observed[-1].detail["pins"] == len(expected)
    assert not native.match("DailyDelivery_AllStarted", (image * 0.7).astype(np.uint8))


@pytest.mark.parametrize("price", ["price", "price2500", "price10000"])
def test_native_dispatch_requires_battery_price_enabled_button_and_page(native, price):
    from pathlib import Path

    positions = {"title": (30, 25), "battery": (371, 1089), "red": (245, 1127),
                 "price": (397, 1084), "text": (262, 1080), "footer": (270, 1195)}
    with np.load(Path(__file__).parent / "fixtures/delivery/controls.npz", allow_pickle=False) as crops:
        image = np.zeros((1280, 720, 3), dtype=np.uint8)
        for key, (x, y) in positions.items():
            crop = crops[price if key == "price" else key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    assert native.match("DailyDelivery_Spend", image)
    assert not native.match("DailyDelivery_Spend", (image * 0.7).astype(np.uint8))
    image[1080:1120, 360:397] = 0
    assert not native.match("DailyDelivery_Spend", image), "No gem or unknown-currency fallback"


def test_dispatch_and_refresh_have_finite_attempts_and_no_completion_shortcut(pipelines):
    spend = pipelines["DailyDelivery_Spend"]
    assert spend["max_hit"] == 36 and spend["next"] == ["DailyDelivery_Verify"]
    assert spend["on_error"] == ["Daily_StopCapture"]
    assert pipelines["DailyDelivery_RefreshSpend"]["max_hit"] == 1
    assert pipelines["DailyDelivery_RefreshSpend"]["anchor"]["DailyDelivery_AfterBatch"] == "Daily_Return"
    assert pipelines["DailyDelivery_Scan"]["next"].index("DailyDelivery_Select") < pipelines["DailyDelivery_Scan"]["next"].index("DailyDelivery_AllStarted")
