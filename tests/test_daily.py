import json
from pathlib import Path

import numpy as np
import pytest
from maa.custom_recognition import CustomRecognition


ROOT = Path(__file__).resolve().parents[1]
TITLE_WIDTHS = dict(Income=201, Friend=309, Delivery=183, VR=398,
                    Contest=219, Gold=331, Gift=368, Gacha=146)


def require_ocr():
    if not all((ROOT / "assets/resource/model/ocr" / name).is_file()
               for name in ("det.onnx", "rec.onnx", "keys.txt")):
        pytest.skip("Native OCR models are not provisioned")


def test_daily_recovery_never_renews_consumption_permits(pipelines):
    assert pipelines["Daily_Start"]["anchor"]["CommonRecoveryResume"] == "Daily_Resume"
    for name in ("Daily_ContestSpend", "Daily_GoldSpend", "Daily_DeliverySpend"):
        assert pipelines[name]["max_hit"] == 1
        assert pipelines[name]["on_error"] == ["Daily_StopCapture"]
    for name, node in pipelines.items():
        if name.startswith("Daily_"):
            assert not any("Spend" in anchor for anchor in node.get("anchor", {}))


@pytest.mark.parametrize("key", ["Income", "Friend", "Delivery", "VR", "Contest", "Gold", "Gift", "Gacha"])
def test_only_pending_rows_can_schedule_work(native, key):
    require_ocr()
    template = ROOT / "assets/resource/image/daily" / f"pending_{key.lower()}.png"
    assert template.is_file()
    # Fixtures contain UI crops only; the native matcher must reject blank/dimmed pages.
    with np.load(ROOT / "tests/fixtures/daily/rows.npz", allow_pickle=False) as crops:
        header, tab, row = crops["header"], crops["tab"], crops[key]
    for y in (340, 560, 780):
        image = np.zeros((1280, 720, 3), dtype=np.uint8)
        image[117:149, 271:450] = header
        image[1018:1067, 45:150] = tab
        image[y:y + row.shape[0], 88:88 + row.shape[1]] = row
        assert native.match(f"Daily_Pending{key}", image)
        assert not native.match(f"Daily_Pending{key}", (image * 0.7).astype(np.uint8))
        with np.load(ROOT / "tests/fixtures/daily/holdout.npz", allow_pickle=False) as holdout:
            x = 88 + TITLE_WIDTHS[key] + 2
            image[y-2:y+30, x:x+60] = 0
            image[y:y+28, x:x+55] = holdout["complete"]
        assert not native.match(f"Daily_Pending{key}", image), "Completed task must never be replayed"
    assert not native.match(f"Daily_Pending{key}", np.zeros_like(image))


def test_later_holdout_uses_separate_strict_progress_and_relative_button(native):
    require_ocr()
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/daily/holdout.npz", allow_pickle=False) as crops:
        image[117:149, 271:450] = crops["header"]
        image[1018:1067, 45:150] = crops["tab"]
        image[340:368, 88:546] = crops["Gold"]
        image[435:480, 493:631] = crops["challenge"]
    assert native.match("Daily_PendingGold", image)
    assert native.resource.override_pipeline({"Daily_ChooseGold": {"enabled": True}})
    assert native.match("Daily_ChooseGold", image)


def test_scan_and_claim_have_shared_finite_limits(pipelines):
    assert 1 <= pipelines["Daily_Scroll"]["max_hit"] <= 64
    assert 1 <= pipelines["Daily_Claim"]["max_hit"] <= 12
    assert pipelines["Daily_Scroll"]["on_error"] == ["Daily_StopCapture"]
    assert pipelines["Daily_Stop"]["action"] == "StopTask"
    assert pipelines["Daily_RewardsReturn"]["next"] == ["[Anchor]Daily_ScanReturn"]


CONTROLS = {
    "prep_title": (52, 42), "contest_prep_free": (52, 1118), "start": (231, 1098),
    "gold_confirm": (285, 181), "gold_coin": (202, 595), "gold_quantity": (348, 660),
    "gold_slider": (233, 698), "gold_submit": (214, 885),
    "delivery_title": (54, 42), "delivery_conditions": (207, 448), "delivery_cost": (231, 1064),
    "exchange_title": (53, 42), "random_tab": (366, 1029),
    "gold_price": (168, 257), "exchange_offer": (161, 307),
    "friend_title": (284, 87), "friend_tab": (81, 1022), "greet": (505, 306),
    "map_title": (52, 43), "complete_pin": (10, 604),
    "win_text": (0, 595), "result_top": (232, 1172),
}
GUARDS = [
    ("ContestSpend", ("prep_title", "contest_prep_free", "start")),
    ("GoldSpend", ("gold_confirm", "gold_coin", "gold_quantity", "gold_slider", "gold_submit")),
    ("DeliverySpend", ("delivery_title", "delivery_conditions", "delivery_cost")),
    ("GoldOffer", ("exchange_title", "random_tab", "gold_price", "exchange_offer")),
    ("FriendGreet", ("friend_title", "friend_tab", "greet")),
    ("DeliveryCollect", ("map_title", "complete_pin")),
    ("BattleResult", ("win_text", "result_top")),
]


def control_frame(keys, missing=None):
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/daily/controls.npz", allow_pickle=False) as crops:
        for key in keys:
            if key == missing:
                continue
            x, y = CONTROLS[key]
            crop = crops[key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return image


@pytest.mark.parametrize("node,keys", GUARDS)
def test_actions_require_observed_complete_bright_controls(native, node, keys):
    if node not in ("FriendGreet", "DeliveryCollect"):
        require_ocr()
    image = control_frame(keys)
    assert native.match("Daily_" + node, image)
    assert not native.match("Daily_" + node, (image * 0.75).astype(np.uint8))
    for key in keys:
        assert not native.match("Daily_" + node, control_frame(keys, missing=key)), (node, key)


@pytest.mark.parametrize("node", ["ContestSpend", "GoldSpend", "DeliverySpend"])
def test_attempt_is_not_reissued_in_same_task_after_returning_to_entry(native, pipelines, node):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    overrides = {name: {"post_delay": 0, "timeout": 20, "rate_limit": 1} for name in pipelines}
    overrides["Daily_" + node].update(recognition="DirectHit", action="Click", target=[350, 1100],
                                       next=["RetryDaily"])
    overrides["RetryDaily"] = {"recognition": "DirectHit", "post_delay": 0,
                                "next": ["Daily_" + node, "Daily_StopCapture"]}
    overrides["Daily_StopCapture"]["action"] = "DoNothing"
    names = [item.name for item in native.run("RetryDaily", overrides).nodes]
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"


def test_remembered_weekly_tab_is_selected_explicitly_before_scanning(native):
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/daily/weekly.npz", allow_pickle=False) as crops:
        image[117:149, 271:450] = crops["header"]
        image[1018:1067, 45:150] = crops["tab"]
        image[1135:1235, 310:410] = crops["close"]
    assert not native.match("Daily_Page", image)
    assert native.match("Daily_SelectTab", image)
    native.controller.image = image
    clicked = []

    def select(x, y):
        clicked.append((x, y))
        with np.load(ROOT / "tests/fixtures/daily/rows.npz", allow_pickle=False) as crops:
            image[1018:1067, 45:150] = crops["tab"]
        return True

    native.controller.on_click = select
    nodes = native.run("Daily_SelectTab", {
        "Daily_SelectTab": {"post_delay": 0},
        "Daily_Top": {"action": "DoNothing", "post_delay": 0, "repeat": 1, "next": ["TabDone"]},
        "TabDone": {"recognition": "DirectHit", "post_delay": 0},
    }).nodes
    assert nodes[-1].name == "TabDone" and len(clicked) == 1
    assert 65 <= clicked[0][0] <= 115 and 1030 <= clicked[0][1] <= 1050


@pytest.mark.parametrize("gate,claim,limit", [
    ("Daily_ClaimGate", "Daily_Claim", 12), ("Daily_Milestone", "Daily_MilestoneClaim", 5),
])
def test_persistent_claim_control_stops_instead_of_falling_through_at_cap(native, gate, claim, limit):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    overrides = {
        gate: {"recognition": "DirectHit", "pre_delay": 0, "post_delay": 0, "timeout": 20},
        claim: {"recognition": "DirectHit", "action": "Click", "target": [350, 450],
                "pre_delay": 0, "post_delay": 0, "next": [gate]},
        "Daily_StopCapture": {"action": "DoNothing", "pre_delay": 0, "post_delay": 0},
        "Daily_Stop": {"pre_delay": 0, "post_delay": 0},
    }
    assert native.run(gate, overrides).nodes[-1].name == "Daily_Stop"
    assert len(clicks) == limit
