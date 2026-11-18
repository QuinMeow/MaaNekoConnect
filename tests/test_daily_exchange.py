from pathlib import Path
from types import SimpleNamespace
import json
import re

import numpy as np
import pytest

from agent.exchange import SLOTS


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {
    "gold_confirm": (285, 181), "gold_coin": (202, 595), "gold_quantity": (348, 660),
    "gold_slider": (233, 698), "gold_submit": (214, 885),
    "exchange_title": (53, 42), "random_tab": (366, 1029),
    "gold_price": (168, 257), "exchange_offer": (161, 307),
}


def control_frame(keys, missing=None):
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/daily/controls.npz", allow_pickle=False) as crops:
        for key in keys:
            if key != missing:
                x, y = CONTROLS[key]
                crop = crops[key]
                image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return image


@pytest.mark.parametrize("node,keys", [
    ("Daily_GoldSpend", ("gold_confirm", "gold_coin", "gold_quantity", "gold_slider", "gold_submit")),
    ("Daily_GoldOffer", ("exchange_title", "random_tab", "exchange_offer", "gold_price")),
])
def test_exchange_requires_known_currency_price_quantity_and_bright_controls(native, node, keys):
    image = control_frame(keys)
    assert native.match(node, image)
    assert not native.match(node, (image * 0.75).astype(np.uint8))
    for key in keys:
        assert not native.match(node, control_frame(keys, missing=key)), key


class Context:
    def __init__(self):
        self.state = {"mode": "page", "slot": 0, "refreshes": 0, "expected": None}
        self.route, self.remaining = None, 5
        self.available = [True] * 4
        self.patches = []
        self.tasker = SimpleNamespace(stopping=False, controller=SimpleNamespace(
            cached_image=np.zeros((1280, 720, 3), dtype=np.uint8),
            post_screencap=lambda: SimpleNamespace(wait=lambda: SimpleNamespace(succeeded=True))))

    def get_node_data(self, name):
        return {"custom_action_param": self.state.copy()}

    def override_pipeline(self, patch):
        self.patches.append(patch)
        if "DailyExchange_State" in patch:
            self.state = patch["DailyExchange_State"]["custom_action_param"]
        return True

    def set_anchor(self, name, target):
        self.route = target
        return True

    def run_recognition(self, name, image):
        if name == "DailyExchange_FreeCount":
            return SimpleNamespace(hit=True, raw_detail={"best": {"text": f"{self.remaining}/5", "score": .99}})
        if name == "Daily_GoldOffer":
            return SimpleNamespace(hit=self.available[self.state["slot"]])
        return SimpleNamespace(hit=True)


def invoke(context, op, **params):
    from agent.exchange import ExchangeControl
    return ExchangeControl().run(context, SimpleNamespace(custom_action_param=json.dumps({"op": op, **params})))


def test_every_page_checks_at_most_four_slots_and_commits_before_opening():
    context = Context()
    for slot in range(4):
        assert invoke(context, "next")
        assert context.state["slot"] == slot + 1 and context.route == "Daily_GoldOffer"
    assert invoke(context, "next") and context.route == "Daily_Return"
    assert context.state["slot"] == 4
    assert not invoke(context, "config", mode="page"), "Re-entry must not renew page permits"


def test_sold_out_slots_are_skipped_without_opening():
    context = Context()
    context.available = [False, False, True, True]
    assert invoke(context, "next")
    assert context.state["slot"] == 3 and context.route == "Daily_GoldOffer"


@pytest.mark.parametrize("observed", [0, 3, 5, 6])
def test_refresh_must_decrease_exactly_once_before_any_new_purchase(observed):
    context = Context()
    context.state.update(mode="free_pages", slot=4)
    assert invoke(context, "next") and context.route == "DailyExchange_RefreshOpen"
    assert context.state["expected"] == 4 and context.state["refreshes"] == 1
    context.remaining = observed
    assert not invoke(context, "verify")
    assert context.state["slot"] == 4


def test_free_updates_are_bounded_and_zero_never_opens_refresh():
    context = Context()
    context.state.update(mode="free_pages", slot=4)
    for remaining in range(5, 0, -1):
        context.remaining = remaining
        assert invoke(context, "next") and context.route == "DailyExchange_RefreshOpen"
        context.remaining -= 1
        assert invoke(context, "verify") and context.state["slot"] == 0
        context.state["slot"] = 4
    assert invoke(context, "next") and context.route == "Daily_Return"
    assert context.state["refreshes"] == 5
    context.remaining = 5
    assert not invoke(context, "next"), "A replenished counter must not renew this task's budget"


def test_non_gold_confirmation_never_reaches_submit(native):
    keys = ("gold_confirm", "gold_quantity", "gold_slider", "gold_submit")
    assert not native.match("Daily_GoldSpend", control_frame(keys))


def test_current_non_gold_dialog_only_closes_without_submitting(native, frame):
    image = frame("daily_exchange", "non_gold_confirm", {
        "title": (270, 165, 190, 65), "close": (310, 1135, 100, 100)})
    assert not native.match("Daily_GoldSpend", image)
    assert native.match("DailyExchange_SkipCurrency", image)
    assert not native.match("DailyExchange_SkipCurrency", (image * 0.7).astype(np.uint8))
    unknown = image.copy()
    unknown[165:230, 270:460] = 0
    assert not native.match("DailyExchange_SkipCurrency", unknown)
    native.controller.image = image
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    names = [node.name for node in native.run("DailyExchange_SkipCurrency", {
        "DailyExchange_SkipCurrency": {"post_delay": 0, "next": []}}).nodes]
    assert names[-1] == "DailyExchange_SkipCurrency" and len(clicks) == 1
    assert 350 <= clicks[0][0] <= 370 and 1175 <= clicks[0][1] <= 1195


def test_consumption_errors_stop_without_recovery_replay(pipelines):
    for name in ("Daily_GoldSpend", "DailyExchange_RefreshOpen", "DailyExchange_RefreshConfirm"):
        assert pipelines[name]["on_error"] == ["Daily_StopCapture"]
    assert pipelines["Daily_GoldSpend"]["anchor"]["CommonRecoveryResume"] == "Daily_StopCapture"


@pytest.mark.parametrize("known", [True, False])
def test_only_source_gold_slots_open_and_each_buys_one(native, frame, pipelines, known):
    regions = {"title": (35, 25, 120, 60), "tab": (350, 1015, 350, 75)}
    for index, (x, y, width, height) in enumerate(SLOTS):
        regions[f"coin{index}"] = (x + 24, y - 40, 40, 36)
        regions[f"offer{index}"] = (x, y, width, height)
    source = frame("daily_exchange", "mixed_currency", regions)
    if not known:
        for index in range(4):
            x, y, width, height = regions[f"coin{index}"]
            source[y:y + height, x:x + width] = 0
    assert not native.match("Daily_GoldOffer", source), "The first slot is not positively gold"
    confirm = control_frame(("gold_confirm", "gold_coin", "gold_quantity", "gold_slider", "gold_submit"))
    reward = frame("daily", "mail_reward", {"reward": (298, 398, 128, 32), "close": (310, 1135, 100, 100)})
    native.controller.image = source
    clicks = []
    def click(x, y):
        clicks.append((x, y))
        native.controller.image = source if y > 1100 else reward if y > 870 else confirm
        return True
    native.controller.on_click = click
    patch = {name: {"post_delay": 0, "timeout": 200, "rate_limit": 1} for name in pipelines}
    patch["Daily_Return"].update(recognition="DirectHit", action="DoNothing", next=[])
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    names = [node.name for node in native.run("DailyExchange_Select", patch).nodes]
    offers = [(x, y) for x, y in clicks if y < 600]
    assert len(offers) == names.count("Daily_GoldSpend") == (3 if known else 0), " > ".join(names)
    assert all(x > 350 or y > 400 for x, y in offers), "Never open the first diamond item"
    assert names[-1] == "Daily_Return"


@pytest.mark.parametrize("paid", [True, False])
def test_free_refresh_confirmation_rejects_paid_markers_even_with_free_text(native, pipelines, paid):
    patch = {
        "DailyExchange_RefreshOpen": {"recognition": "DirectHit", "action": "DoNothing", "post_delay": 0},
        "DailyExchange_RefreshDialogTitle": {"recognition": "DirectHit"},
        "DailyExchange_RefreshConfirmGuard": {"recognition": "DirectHit"},
        "DailyExchange_RefreshPaidText": {"recognition": "DirectHit" if paid else "OCR",
                                          "roi": [0, 0, 40, 40], "expected": ["paid"]},
        "DailyExchange_RefreshConfirm": {"action": "DoNothing", "post_delay": 0, "next": []},
        "Daily_PostError": {"enabled": False},
        "Daily_StopCapture": {"action": "DoNothing", "post_delay": 0, "next": []},
    }
    names = [node.name for node in native.run("DailyExchange_RefreshOpen", patch).nodes]
    assert names[-1] == ("Daily_StopCapture" if paid else "DailyExchange_RefreshConfirm")
    assert ("DailyExchange_RefreshConfirm" in names) is not paid
    expected = pipelines["DailyExchange_RefreshPaidText"]["expected"][0]
    for marker in ("有料", "有償", "ジュエル", "ダイヤ", "消費", "所持", "100個", "100"):
        assert re.search(expected, marker)
