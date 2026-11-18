from pathlib import Path

import numpy as np
import pytest
from maa.context import ContextEventSink

from agent.contest import parse_rating, refresh_decision


ROOT = Path(__file__).resolve().parents[1]
CONTROLS = {
    "prep_title": (52, 42), "contest_prep_free": (52, 1118), "start": (231, 1098),
    "win_text": (0, 595), "result_top": (232, 1172),
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
    ("Daily_ContestSpend", ("prep_title", "contest_prep_free", "start")),
    ("Daily_BattleResult", ("win_text", "result_top")),
])
def test_contest_actions_require_complete_bright_controls(native, node, keys):
    image = control_frame(keys)
    assert native.match(node, image)
    assert not native.match(node, (image * 0.75).astype(np.uint8))
    for key in keys:
        assert not native.match(node, control_frame(keys, missing=key)), key


def test_observed_failed_result_requires_title_top_and_brightness_then_closes_once(native, frame):
    regions = {"title": (0, 595, 510, 135), "top": (215, 1155, 290, 90)}
    image = frame("daily", "contest_failed", regions)
    title = image[595:730, :510]
    masked = np.all(title == [0, 255, 0], axis=2)
    assert masked.any()
    title[masked] = np.random.default_rng(17).integers(0, 256, (masked.sum(), 3), dtype=np.uint8)
    assert native.match("Daily_BattleResult", image)
    for name, (x, y, width, height) in regions.items():
        partial = image.copy()
        partial[y:y + height, x:x + width] = 0
        assert not native.match("Daily_BattleResult", partial), name
    assert not native.match("Daily_BattleResult", (image * 0.7).astype(np.uint8))
    native.controller.image = image
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    names = [node.name for node in native.run("Daily_BattleResult", {
        "Daily_BattleResult": {"post_delay": 0, "next": []}}).nodes]
    assert names[-1] == "Daily_BattleResult" and len(clicks) == 1
    assert 232 <= clicks[0][0] <= 488 and 1172 <= clicks[0][1] <= 1232


def test_shared_win_glyph_ignores_background_and_rejects_defeat(native, frame, pipelines):
    # Isolate the native glyph fallback so successful OCR cannot hide a broken mask.
    assert native.resource.override_pipeline({"DailyCore_WinText": {
        "any_of": [pipelines["DailyCore_WinText"]["any_of"][1]]}})
    image = frame("daily_gift", "result_right", {"win": (0, 595, 350, 130), "ok": (220, 1155, 290, 90)})
    win = image[595:725, :350]
    blue, green, red = np.moveaxis(win, -1, 0)
    orange = (blue < 145) & (green >= 135) & (green <= 230) & (red >= 245)
    near, padded = np.zeros_like(orange), np.pad(orange, 5)
    for dy in range(11):
        for dx in range(11):
            near |= padded[dy:dy + 130, dx:dx + 350]
    keep = orange | ((np.min(win, axis=2) >= 240) & near)
    keep[:40, 195:280] = False
    assert keep.any() and (~keep).any()
    win[~keep] = np.random.default_rng(17).integers(0, 256, ((~keep).sum(), 3), dtype=np.uint8)
    assert native.match("DailyCore_WinText", image)
    defeat = frame("daily", "contest_failed", {"title": (0, 595, 510, 135), "top": (215, 1155, 290, 90)})
    assert not native.match("DailyCore_WinText", defeat)


def test_free_contest_attempt_is_not_reissued_after_returning_to_entry(native, pipelines):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    patch = {name: {"post_delay": 0, "timeout": 20, "rate_limit": 1} for name in pipelines}
    patch["Daily_ContestSpend"].update(recognition="DirectHit", action="Click", target=[350, 1100],
                                      next=["RetryContest"])
    patch["RetryContest"] = {"recognition": "DirectHit", "post_delay": 0,
                              "next": ["Daily_ContestSpend", "Daily_StopCapture"]}
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    names = [item.name for item in native.run("RetryContest", patch).nodes]
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"


@pytest.mark.parametrize("text,value", [("6,424K", 6424000), ("5.5M", 5500000), ("4500", 4500)])
def test_opponent_rating_units(text, value):
    assert parse_rating(text, 0.99) == value


@pytest.mark.parametrize("text,score", [("?", 0.99), ("6,424K", 0.4), ("-1", 0.99)])
def test_uncertain_rating_cannot_authorize_refresh(text, score):
    with pytest.raises(ValueError):
        parse_rating(text, score)


def test_rating_refresh_requires_strictly_lower_score_and_confirmed_decrement():
    assert refresh_decision(100, 100, 3, None) == "refresh"
    assert refresh_decision(99, 100, 2, 3) == "select"
    assert refresh_decision(101, 100, 0, 1) == "select"
    for quota in (3, 1, None):
        with pytest.raises(ValueError):
            refresh_decision(101, 100, quota, 3)


@pytest.mark.parametrize("position,ratings,quotas,refreshes,stops", [
    ("top", (200, 150, 90), (3, 2, 1), 2, False),
    ("middle", (200, 150, 110, 100), (3, 2, 1, 0), 3, False),
    ("bottom", (200,), (0,), 0, False),
    ("top", (200, 150), (3, 3), 1, True),
])
def test_arena_refreshes_until_lower_or_free_exhaustion(native, pipelines, monkeypatch,
                                                       position, ratings, quotas, refreshes, stops):
    clicks, messages = [], []
    current = 0

    class Sink(ContextEventSink):
        def on_raw_notification(self, context, message, details):
            if message == "Node.Action.Succeeded" and details["name"] == "DailyContest_Log":
                messages.append(details["focus"]["Node.Action.Succeeded"])

    native.tasker.add_context_sink(Sink())
    def ocr(context, node):
        return (str(ratings[current]) if node.endswith("RatingOCR") else f"あと{quotas[current]}回", 1.0)
    monkeypatch.setattr("agent.contest._ocr", ocr)
    def click(x, y):
        nonlocal current
        clicks.append((x, y))
        if y < 800:
            current += 1
        return True
    native.controller.on_click = click
    patch = {name: {"post_delay": 0, "timeout": 20, "rate_limit": 1} for name in pipelines}
    for node in ("Daily_ContestBegin", "DailyContest_Refresh", "Daily_ContestOpponent"):
        patch[node]["recognition"] = "DirectHit"
    patch["DailyContest_PositionConfig"]["custom_action_param"] = {"op": "position", "position": position}
    patch["DailyContest_ThresholdConfig"]["custom_action_param"] = {"op": "threshold", "threshold": 100}
    patch["NavHome_Ensure"].update(recognition="DirectHit", action="DoNothing", next=["Daily_ContestBegin"])
    patch["Daily_ContestOpponent"]["next"] = []
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    names = [item.name for item in native.run("DailyContest_PositionConfig", patch).nodes]
    assert sum(y < 800 for x, y in clicks) == refreshes
    assert len(clicks) == refreshes + (not stops)
    assert names[-1] == ("Daily_Stop" if stops else "Daily_ContestOpponent")
    if not stops:
        assert {"top": 850, "middle": 965, "bottom": 1080}[position] <= clicks[-1][1] <= 1100
    assert messages and "200" in messages[0]


def test_refresh_rechecks_current_free_quota_before_click(native, pipelines, monkeypatch):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    monkeypatch.setattr("agent.contest._free_refreshes", lambda context: 0)
    patch = {name: {"post_delay": 0, "timeout": 20, "rate_limit": 1} for name in pipelines}
    patch["DailyContest_State"] = {"custom_action_param": {
        "position": "top", "threshold": 100, "previous": None, "quota": 3}}
    patch["DailyContest_Refresh"]["recognition"] = "DirectHit"
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    names = [item.name for item in native.run("DailyContest_Refresh", patch).nodes]
    assert not clicks and names[-1] == "Daily_Stop"
