import json
from pathlib import Path
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
        self.state = {"selected": None, "started": [], "refresh_seen": None}
        self.tasker = NS(stopping=False)
        self.save_ok = True

    def get_node_data(self, name):
        return {"custom_recognition_param": self.state} if name == delivery.STATE_NODE else {"threshold": 0.95}

    def override_pipeline(self, patch):
        self.state = patch[delivery.STATE_NODE]["custom_recognition_param"]
        return self.save_ok

    def clone(self):
        return NS(run_recognition=self.run_recognition)

    def run_recognition(self, name, image, pipeline_override=None):
        if name == "DailyDelivery_Pins":
            return NS(hit=bool(self.boxes), filtered_results=[],
                      all_results=[NS(box=box, score=0.99) for box in self.boxes])
        if name == "DailyDelivery_OrderCount":
            return result(True, [NS(text=self.text, score=self.score)])
        roi = pipeline_override[name]["roi"]
        index = min(range(len(self.statuses)), key=lambda i: abs(self.boxes[i][0] + 16 - roi[0] - roi[2] // 2))
        status = self.statuses[index]
        if name == "DailyDelivery_Status":
            texts = {"running": "01:02:03", "neighbor_timer": "01:02:03", "foreign_timer": "01:02:03",
                     "complete": "配達完了!", "bad_timer": "01:62:03"}
            box = [self.boxes[index][0] + (70 if status == "foreign_timer" else -30), 393, 92, 22]
            return result(status in texts, [NS(text=texts.get(status, ""), score=0.99, box=box)])
        cap = NS(box=[self.boxes[index][0] + (30 if status == "foreign_timer" else -50), 393, 18, 26], score=0.99)
        return result(status in {"running", "foreign_timer", "complete", "unknown", "bad_timer"}, [cap] if status in ("running", "foreign_timer") else [])


def probe(context, op):
    return delivery.DailyDeliveryMapProbe().analyze(context, NS(
        custom_recognition_param=json.dumps({"op": op}),
        image=np.ones((1280, 720, 3), dtype=np.uint8), roi=(0, 0, 720, 1280)))


@pytest.mark.parametrize("shift", [-24, -21, 0, 20, 21, 24])
def test_selection_deduplicates_and_preserves_dispatch_history_through_animation_and_refresh(shift):
    context = Context(["running", "complete", "pending"])
    assert tuple(probe(context, "select").box) == (540, 450, 32, 40)
    assert probe(context, "select") is None
    assert probe(context, "started") is None and probe(context, "verify") is None
    context.statuses[2] = "running"
    context.boxes[0][0], context.boxes[2][0] = 527, 553  # Two distinct pins bracket the selection by 13px.
    assert probe(context, "verify") is None
    context.boxes[0][0], context.boxes[2][0] = 180, 540 + shift
    assert probe(context, "verify") is not None and context.state["selected"] is None
    assert probe(context, "verify") is None
    context.statuses[2] = "timer_missed"
    assert probe(context, "select") is None
    assert probe(context, "started") is not None
    assert probe(context, "refresh_prepare") is not None
    context.boxes[2][0] -= shift
    assert probe(context, "refreshed") is None
    context.statuses.append("pending")
    context.boxes.append([80, 750, 32, 40])
    context.text = "4/18件"
    assert probe(context, "refreshed") is not None and context.state["started"] == [[196, 470], [556, 470]]


@pytest.mark.parametrize("statuses,text,expected", [([], "0/18件", True),
    (["running"], "1/18件", True),
    (["neighbor_timer"], "1/18件", True), (["foreign_timer"], "1/18件", False),
    (["running", "complete"], "2/18件", True), (["pending"], "1/18件", False),
    (["unknown"], "1/18件", False), (["bad_timer"], "1/18件", False),
    (["running"], "0/18件", False), ([], "6/18件", False),
    (["running"], "19/18件", False), (["running"], "1/18", False)])
def test_refresh_requires_a_complete_known_map_without_pending_orders(statuses, text, expected):
    context = Context(statuses)
    context.text = text
    assert (probe(context, "started") is not None) is expected
    assert (probe(context, "paid_ready") is not None) is bool(expected and statuses and set(statuses) == {"running"})
    assert (probe(context, "paid_prepare") is not None) is bool(expected and statuses and set(statuses) == {"running"})


@pytest.mark.parametrize("case", ["unknown", "bad_timer", "count_mismatch", "low_score", "stopped", "save_failed",
                                 "pins_none", "pins_empty"])
def test_unknown_or_incomplete_native_evidence_never_authorizes_selection(case):
    pins = case.startswith("pins_")
    context = Context([] if pins else [case if case in ("unknown", "bad_timer") else "pending"])
    context.text = "0/18件" if case == "count_mismatch" else context.text
    context.score = 0.94 if case == "low_score" else 0.99
    context.tasker.stopping = case == "stopped"
    context.save_ok = case != "save_failed"
    if pins:
        original = context.run_recognition
        context.run_recognition = lambda name, image, patch=None: (
            (None if case == "pins_none" else result(True)) if name == "DailyDelivery_Pins" else original(name, image, patch))
    assert probe(context, "started" if pins else "select") is None


@pytest.mark.parametrize("sample,entry,expected", [
    ("new", "Select", ["pending"] * 6),
    ("running", "Select", ["pending"] * 5 + ["running"]),
    ("completed", "AllStarted", ["complete"] * 5 + ["running"]), ("empty", "AllStarted", []),
    ("all_busy_current", "AllStarted", ["running"] * 5),
    ("mixed_eleven", "Select", ["running"] * 5 + ["pending"] * 6),
    ("animated_eleven", "Select", ["running"] * 5 + ["pending"] * 6),
    ("counter_occluded", "Select", ["running"] * 4 + ["pending"] * 5),
    ("counter_and_glyph_occluded", "Select", ["running"] * 6 + ["pending"] * 3),
    ("all_started_counter_occluded", "AllStarted", ["running"] * 9),
    ("initial_running_current", "Select", ["running"] + ["pending"] * 4),
    ("two_running_after_dispatch", "Select", ["running"] * 2 + ["pending"] * 3),
    ("paid_before", "PaidRefreshPermit", ["running"] * 5 + ["pending"] * 6),
    ("eight_running_current", "Select", ["running"] * 8 + ["pending"] * 3),
])
def test_native_map_probe_accounts_for_every_observed_pin(native, frame, sample, entry, expected):
    observed = []

    class Observe(delivery.DailyDeliveryMapProbe):
        def analyze(self, context, argv):
            value = super().analyze(context, argv)
            if entry == "PaidRefreshPermit" and value is not None:
                value = super().analyze(context, NS(image=frame("delivery", "paid_after", regions),
                                                   custom_recognition_param='{"op":"refreshed"}'))
                value = value if value is not None and len(delivery._state(context)["started"]) == 5 else None
            observed.append(value)
            return value

    assert native.resource.register_custom_recognition("DailyDeliveryMapProbe", Observe())
    regions = {"title": (35, 25, 190, 60), "count": (530, 102, 180, 38),
               "map": (0, 100, 710, 900), "footer": (270, 1195, 180, 80), "refresh": (142, 1060, 208, 100)}
    image = frame("delivery", sample, regions)
    assert native.match("DailyDelivery_" + entry, image, seconds=10)
    assert sorted(observed[-1].detail["states"]) == sorted(expected)
    assert not native.match("DailyDelivery_AllStarted", (image * 0.7).astype(np.uint8), seconds=10)
    if sample == "counter_occluded":
        for region in ((530, 115, 140, 35), (532, 465, 40, 38), (532, 515, 40, 35)):
            changed = image.copy()
            x, y, width, height = region
            changed[y:y + height, x:x + width] = 0
            assert not native.match("DailyDelivery_Select", changed)


@pytest.mark.parametrize("sample", ["dispatch1000", "dispatch2500", "dispatch10000", "paid100", "paid1000", "speedup"])
def test_native_dispatch_and_refresh_require_exact_currency_price_and_confirmation(native, sample):
    paid = not sample.startswith("dispatch")
    node = "DailyDelivery_PaidRefreshSpend" if paid else "DailyDelivery_Spend"
    with np.load(Path(__file__).parent / "fixtures/delivery/action_controls.npz", allow_pickle=False) as crops:
        image = crops[sample].copy()
    valid = sample not in ("paid1000", "speedup")
    assert native.match(node, image) is valid
    if not valid:
        return
    assert not native.match(node, (image * 0.7).astype(np.uint8))
    x, y, width, height = (192, 534, 48, 44) if paid else (360, 1080, 37, 40)
    image[y:y + height, x:x + width] = 0
    assert not native.match(node, image), "The exact currency icon is required"


@pytest.mark.parametrize("transient,expected", [(True, "Select"), (False, "StopCapture"), (None, "Verify")])
def test_scan_handles_animation_and_speedup_without_spending(native, transient, expected):
    calls = []

    class Probe(delivery.CustomRecognition):
        def analyze(self, context, argv):
            calls.append(1)
            return self.AnalyzeResult(box=(0, 0, 1, 1), detail={}) if transient and len(calls) > 1 else None

    assert native.resource.register_custom_recognition("RetryProbe", Probe())
    patch = {"DailyDelivery_Scan": {"recognition": "DirectHit", "post_delay": 0},
             "Daily_PostError": {"recognition": "DirectHit", "inverse": True},
             "DailyDelivery_CollectGate": {"recognition": "DirectHit", "inverse": True},
             "DailyDelivery_AllStarted": {"recognition": "DirectHit", "inverse": True},
             "DailyDelivery_Select": {"recognition": "Custom", "custom_recognition": "RetryProbe",
                                      "action": "DoNothing", "post_delay": 0, "next": []},
             "DailyDelivery_RetryScan": {"post_delay": 0},
             "Daily_StopCapture": {"action": "DoNothing", "next": []}}
    if transient is None:
        with np.load(Path(__file__).parent / "fixtures/delivery/speedup_close.npz", allow_pickle=False) as crops:
            native.controller.image = crops["image"].copy()
        native.controller.on_click = lambda x, y: 330 <= x <= 390 and 1150 <= y <= 1220
        patch["DailyDelivery_Select"] = {"recognition": "DirectHit", "action": "DoNothing", "post_delay": 0}
        patch["DailyDelivery_Verify"] = {"recognition": "DirectHit", "next": []}
    names = [node.name for node in native.run("DailyDelivery_Select" if transient is None else "DailyDelivery_Scan", patch).nodes]
    assert names[-1] == ("Daily_StopCapture" if expected == "StopCapture" else "DailyDelivery_" + expected)
    assert not any(name.endswith("Spend") or name.endswith("Refresh") for name in names)
    assert "DailyDelivery_CloseSpeedup" in names if transient is None else 2 <= len(calls) <= 8
