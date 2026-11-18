from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_reward_on_blue_background_requires_title_and_bright_close(native, frame):
    image = frame("daily", "vr_reward_current", {
        "title": (270, 380, 180, 70), "close": (310, 1135, 100, 100)})
    assert native.match("Daily_DismissReward", image)
    assert not native.match("Daily_DismissReward", (image * 0.7).astype(np.uint8))
    image[380:450, 270:450] = 0
    assert not native.match("Daily_DismissReward", image)


def test_remembered_weekly_tab_is_selected_before_claiming_daily_rewards(native):
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
        with np.load(ROOT / "tests/fixtures/daily/controls.npz", allow_pickle=False) as crops:
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
    patch = {
        gate: {"recognition": "DirectHit", "pre_delay": 0, "post_delay": 0, "timeout": 20},
        claim: {"recognition": "DirectHit", "action": "Click", "target": [350, 450],
                "pre_delay": 0, "post_delay": 0, "next": [gate]},
        "Daily_StopCapture": {"action": "DoNothing", "pre_delay": 0, "post_delay": 0},
        "Daily_Stop": {"pre_delay": 0, "post_delay": 0},
    }
    assert native.run(gate, patch).nodes[-1].name == "Daily_Stop"
    assert len(clicks) == limit
