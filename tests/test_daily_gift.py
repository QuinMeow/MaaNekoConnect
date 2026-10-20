import maa  # Cache native platform metadata before the offline process guard.
import numpy as np
import pytest


REGIONS = {
    "title": (35, 25, 185, 60), "quota": (254, 116, 60, 35),
    "rows": (40, 173, 640, 878), "bar": (694, 173, 12, 885),
    "tab": (30, 1090, 325, 50), "home": (280, 1195, 160, 75),
    "prep": (35, 25, 155, 60), "start": (220, 1085, 280, 90),
    "quick": (500, 1113, 152, 32), "win": (0, 595, 350, 130),
    "ok": (220, 1155, 290, 90), "quest_title": (0, 20, 250, 80),
}


def overrides(pipelines):
    result = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 40, "rate_limit": 1}
              for name in pipelines}
    result["Daily_StopCapture"]["action"] = "DoNothing"
    return result


def test_selected_gift_uses_quest_without_reading_a_pending_daily_row(pipelines):
    anchor = pipelines["DailyGift_Start"]["anchor"]
    assert anchor["NavHome_Return"] == "DailyCore_Quest"
    assert anchor["DailyCore_QuestTarget"] == "DailyGift_Open"
    assert "Daily_Page" not in pipelines["DailyGift_Open"]["all_of"]
    assert "DailyCore_QuestPage" in pipelines["DailyGift_Open"]["all_of"]


@pytest.mark.parametrize("remove_last,low,high", [(False, 940, 1000), (True, 700, 790)])
def test_lowest_cleared_marker_selects_its_own_prepare_button(native, frame, pipelines, remove_last, low, high):
    image = frame("daily_gift", "bottom", REGIONS)
    if remove_last:
        image[930:1030, 65:160] = 0
    native.controller.image = image
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    patch = overrides(pipelines)
    patch["DailyGift_Prepare"]["next"] = []
    nodes = native.run("DailyGift_Prepare", patch).nodes
    assert nodes[-1].name == "DailyGift_Prepare" and len(clicks) == 1
    assert 520 <= clicks[0][0] <= 665 and low <= clicks[0][1] <= high, nodes[-1].recognition.raw_detail


@pytest.mark.parametrize("missing", ["bar", "quota", "tab", "home", "rows"])
def test_prepare_needs_bottom_quota_cleared_marker_and_correct_page(native, frame, missing):
    image = frame("daily_gift", "bottom", REGIONS)
    x, y, width, height = REGIONS[missing]
    image[y:y + height, x:x + width] = 0
    assert not native.match("DailyGift_Prepare", image)
    assert not native.match("DailyGift_Prepare", frame("daily_gift", "bottom", REGIONS) * np.uint8(0))


def test_dimmed_or_unconfirmed_bottom_is_not_authorized(native, frame):
    image = frame("daily_gift", "bottom", REGIONS)
    assert not native.match("DailyGift_Prepare", (image * 0.75).astype(np.uint8))
    image[1028:1056, 694:706] = image[975:1003, 694:706]
    assert not native.match("DailyGift_Prepare", image)


@pytest.mark.parametrize("erase", [False, True])
def test_a_valid_higher_row_cannot_authorize_a_missing_or_dimmed_lowest_button(native, frame, erase):
    image = frame("daily_gift", "bottom", REGIONS)
    image[940:1005, 510:670] = 0 if erase else (image[940:1005, 510:670] * 0.7).astype(np.uint8)
    assert not native.match("DailyGift_Prepare", image)


def test_zero_attempts_is_distinct_from_unknown_and_cannot_prepare(native, frame):
    image = frame("daily_gift", "zero", REGIONS)
    assert native.match("DailyGift_Exhausted", image)
    assert not native.match("DailyGift_Prepare", image)
    image[116:151, 254:314] = 0
    assert not native.match("DailyGift_Exhausted", image)


def test_quick_spend_requires_checked_not_unchecked_or_missing_controls(native, frame):
    checked = frame("daily_gift", "checked", REGIONS)
    unchecked = frame("daily_gift", "unchecked", REGIONS)
    assert native.match("DailyGift_QuickSpend", checked)
    assert not native.match("DailyGift_QuickSpend", unchecked)
    assert native.match("DailyGift_EnableQuick", unchecked)
    assert not native.match("DailyGift_EnableQuick", checked)
    for key in ("prep", "start", "quick"):
        image = checked.copy()
        x, y, width, height = REGIONS[key]
        image[y:y + height, x:x + width] = 0
        assert not native.match("DailyGift_QuickSpend", image)
    assert not native.match("DailyGift_QuickSpend", (checked * 0.75).astype(np.uint8))


@pytest.mark.parametrize("initial", ["checked", "unchecked"])
def test_quick_flow_confirms_toggle_spends_once_and_uses_ok_not_again(native, frame, pipelines, initial):
    images = {name: frame("daily_gift", name, REGIONS)
              for name in ("checked", "unchecked", "result", "zero")}
    home = frame("navigation", "home_ready", {
        "home_building": (535, 1105, 140, 110), "home_label": (530, 1205, 155, 65),
    })
    native.controller.image = images[initial]
    clicks = []

    def click(x, y):
        clicks.append((x, y))
        if native.controller.image is images["unchecked"]:
            assert 505 <= x <= 526 and 1117 <= y <= 1138
            native.controller.image = images["checked"]
        elif native.controller.image is images["checked"]:
            native.controller.image = images["result"]
        elif native.controller.image is images["result"]:
            assert 232 <= x <= 488 and 1172 <= y <= 1231
            native.controller.image = images["zero"]
        else:
            native.controller.image = home
        return True

    native.controller.on_click = click
    names = [node.name for node in native.run("DailyGift_PrepDispatch", overrides(pipelines)).nodes]
    assert names[-1] == "DailyCore_Done", names
    assert names.count("DailyGift_QuickSpend") == names.count("DailyGift_ResultOK") == 1
    assert len(clicks) == (4 if initial == "unchecked" else 3)
    assert all(not (x > 500 and y > 1160) for x, y in clicks)


def test_failed_quick_toggle_stops_without_trying_a_consumption(native, frame, pipelines):
    native.controller.image = frame("daily_gift", "unchecked", REGIONS)
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    names = [node.name for node in native.run("DailyGift_PrepDispatch", overrides(pipelines)).nodes]
    assert len(clicks) == 1 and "DailyGift_QuickSpend" not in names
    assert names[-1] == "Daily_Stop"


@pytest.mark.parametrize("missing", ["win", "ok"])
def test_win_and_main_ok_are_both_required_for_result_ack(native, frame, missing):
    image = frame("daily_gift", "result", REGIONS)
    assert native.match("DailyGift_ResultOK", image)
    x, y, width, height = REGIONS[missing]
    image[y:y + height, x:x + width] = 0
    assert not native.match("DailyGift_ResultOK", image)


def test_spend_budget_cannot_fall_through_or_replay_in_the_same_task(native, pipelines):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    patch = overrides(pipelines)
    patch["DailyGift_QuickSpend"].update(recognition="DirectHit", action="Click", target=[360, 1128],
                                        next=["GiftRetry"])
    patch["GiftRetry"] = {"recognition": "DirectHit", "post_delay": 0,
                          "next": ["DailyGift_QuickSpend", "Daily_StopCapture"]}
    names = [node.name for node in native.run("GiftRetry", patch).nodes]
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"
    assert pipelines["DailyGift_QuickSpend"]["max_hit"] == 1
    assert pipelines["DailyGift_QuickSpend"]["on_error"] == ["Daily_StopCapture"]


def test_search_can_authorize_a_middle_view_only_after_proving_bottom(native, frame, pipelines):
    bottom = frame("daily_gift", "bottom", REGIONS)
    middle = bottom.copy()
    middle[173:1058, 694:706] = 0
    assert not native.match("DailyGift_Prepare", middle)
    bottom[220:1040, 65:160] = 0
    native.controller.image = bottom
    swipes, clicks = [], []
    def swipe(*args):
        swipes.append(args)
        native.controller.image = middle
        return True
    native.controller.swipe = swipe
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    patch = overrides(pipelines)
    patch["DailyGift_Prepare"]["next"] = []
    names = [node.name for node in native.run("DailyGift_BottomProved", patch).nodes]
    assert names[-1] == "DailyGift_Prepare" and len(swipes) == len(clicks) == 1
    assert 940 <= clicks[0][1] <= 1000 and swipes[0][3] > swipes[0][1]
    patch["NavHome_Ensure"].update(recognition="DirectHit", action="DoNothing", next=[])
    native.run("DailyGift_Start", patch)
    assert not native.match("DailyGift_Prepare", middle), "A new task cannot inherit bottom proof"


def test_visible_clear_with_incomplete_prepare_stops_instead_of_searching_past_it(native, frame, pipelines):
    image = frame("daily_gift", "bottom", REGIONS)
    image[940:1005, 510:670] = 0
    native.controller.image = image
    native.controller.swipe = lambda *args: pytest.fail("Must not skip the highest visible cleared row")
    names = [node.name for node in native.run("DailyGift_BottomProved", overrides(pipelines)).nodes]
    assert names[-1] == "Daily_Stop" and "DailyGift_SearchUp" not in names


def test_no_clear_search_has_a_shared_finite_swipe_budget(native, frame, pipelines):
    native.controller.image = frame("daily_gift", "bottom", REGIONS)
    swipes = []
    native.controller.swipe = lambda *args: swipes.append(args) or True
    patch = overrides(pipelines)
    patch["DailyGift_SearchReady"]["recognition"] = "DirectHit"
    patch["DailyGift_HasClearedGate"]["enabled"] = False
    patch["DailyGift_SearchUp"]["max_hit"] = 3
    names = [node.name for node in native.run("DailyGift_BottomProved", patch).nodes]
    assert len(swipes) == 3 and names[-1] == "Daily_Stop"
    assert 0 < pipelines["DailyGift_SearchUp"]["max_hit"] <= 8
