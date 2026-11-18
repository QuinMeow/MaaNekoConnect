import maa  # Cache native platform metadata before the offline process guard.
import numpy as np
import pytest

from agent.gift import new_budget


REGIONS = {
    "title": (35, 25, 185, 60), "quota": (254, 116, 60, 35),
    "rows": (40, 173, 640, 878), "bar": (694, 173, 12, 885),
    "tab": (30, 1090, 325, 50), "home": (280, 1195, 160, 75),
    "prep": (35, 25, 155, 60), "start": (220, 1085, 280, 90),
    "quick": (500, 1113, 152, 32), "win": (0, 595, 350, 130),
    "ok": (220, 1155, 290, 90), "quest_title": (0, 20, 250, 80),
}


def overrides(pipelines, timeout=40):
    result = {name: {"pre_delay": 0, "post_delay": 0, "timeout": timeout, "rate_limit": 1}
              for name in pipelines}
    result["Daily_StopCapture"]["action"] = "DoNothing"
    state = new_budget(1, 0)
    state.update(side=0, quota=1, ready=True)
    result["DailyGift_State"] = {"custom_action_param": state}
    return result


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


@pytest.mark.parametrize("sample,node,required", [
    ("bottom", "DailyGift_Prepare", ("bar", "quota", "tab", "home", "rows")),
    ("checked", "DailyGift_QuickSpend", ("prep", "start", "quick")),
    ("result", "DailyGift_ResultOK", ("win", "ok")),
])
def test_actions_require_complete_bright_controls(native, frame, sample, node, required):
    image = frame("daily_gift", sample, REGIONS)
    assert not native.match(node, (image * 0.7).astype(np.uint8))
    for key in required:
        partial = image.copy()
        x, y, width, height = REGIONS[key]
        partial[y:y + height, x:x + width] = 0
        assert not native.match(node, partial), key
    assert not native.match(node, np.zeros_like(image))
    assert not native.match("DailyGift_Prepare", frame("daily_gift", "zero", REGIONS))


@pytest.mark.parametrize("erase", [False, True])
def test_a_valid_higher_row_cannot_authorize_a_missing_or_dimmed_lowest_button(native, frame, erase):
    image = frame("daily_gift", "bottom", REGIONS)
    image[940:1005, 510:670] = 0 if erase else (image[940:1005, 510:670] * 0.7).astype(np.uint8)
    assert not native.match("DailyGift_Prepare", image)


@pytest.mark.parametrize("quotas,total", [
    ((3, 2, 1, 0, 3, 2, 1, 0), 6), ((3, 3), 1),
])
def test_both_tabs_repeat_only_after_confirmed_results(native, frame, pipelines, monkeypatch, quotas, total):
    images = {name: frame("daily_gift", name, REGIONS)
              for name in ("checked", "unchecked", "result", "bottom")}
    values = iter(quotas)
    monkeypatch.setattr("agent.gift._read_quota", lambda context, state: next(values))
    home = frame("navigation", "home_ready", {
        "home_building": (535, 1105, 140, 110), "home_label": (530, 1205, 155, 65),
    })
    native.controller.image = images["bottom"]
    no_clear = images["bottom"].copy()
    no_clear[220:1040, 65:160] = 0
    clicks, searches = [], []

    def click(x, y):
        clicks.append((x, y))
        if native.controller.image is images["unchecked"]:
            assert 505 <= x <= 526 and 1117 <= y <= 1138
            native.controller.image = images["checked"]
        elif native.controller.image is images["checked"]:
            native.controller.image = images["result"]
        elif native.controller.image is images["result"]:
            assert 232 <= x <= 488 and 1172 <= y <= 1231
            native.controller.image = images["bottom"]
        elif y > 1200:
            native.controller.image = home
        elif y < 1080:
            native.controller.image = images["unchecked"]
        else:
            native.controller.image = images["bottom"]
        return True

    native.controller.on_click = click
    def swipe(x1, y1, x2, y2, *args):
        if y2 > y1:
            searches.append((x1, y1, x2, y2))
        native.controller.image = images["bottom"] if y2 > y1 and len(searches) % 2 == 0 else no_clear
        return True
    native.controller.swipe = swipe
    patch = overrides(pipelines)
    state = new_budget()
    state["side"] = 0
    patch["DailyGift_State"] = {"custom_action_param": state}
    names = [node.name for node in native.run("DailyGift_ReadList", patch).nodes]
    assert names[-1] == ("Daily_Stop" if total == 1 else "DailyCore_Done"), names
    assert names.count("DailyGift_QuickSpend") == names.count("DailyGift_ResultOK") == total
    assert names.count("DailyGift_EnableQuick") == total and len(searches) == total * 2
    assert all(not (x > 500 and y > 1160) for x, y in clicks)


def test_failed_quick_toggle_stops_without_trying_a_consumption(native, frame, pipelines):
    native.controller.image = frame("daily_gift", "unchecked", REGIONS)
    assert not native.match("DailyGift_QuickSpend", native.controller.image)
    assert native.match("DailyGift_EnableQuick", native.controller.image)
    assert not native.match("DailyGift_EnableQuick", frame("daily_gift", "checked", REGIONS))
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    names = [node.name for node in native.run("DailyGift_PrepDispatch", overrides(pipelines)).nodes]
    assert len(clicks) == 1 and "DailyGift_QuickSpend" not in names
    assert names[-1] == "Daily_Stop"


def test_spend_budget_cannot_fall_through_or_replay_in_the_same_task(native, pipelines):
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    patch = overrides(pipelines)
    patch["DailyGift_QuickSpend"].update(recognition="DirectHit", next=["GiftRetry"])
    patch["GiftRetry"] = {"recognition": "DirectHit", "post_delay": 0,
                          "next": ["DailyGift_QuickSpend", "Daily_StopCapture"]}
    names = [node.name for node in native.run("GiftRetry", patch).nodes]
    assert len(clicks) == 1 and names[-1] == "Daily_Stop"
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
    names = [node.name for node in native.run("DailyGift_BottomProved", patch).nodes]
    assert len(swipes) == 8 and names[-1] == "Daily_Stop"


@pytest.mark.parametrize("entry,target,sample", [
    ("DailyGift_SelectGate", "DailyGift_BottomProved", "bottom"),
    ("DailyGift_PrepDispatch", "DailyGift_CheckedGate", "checked"),
    ("DailyGift_ResultGate", "DailyGift_ResultOK", "result_right"),
])
@pytest.mark.parametrize("ready", [True, False])
def test_transitions_wait_bounded(native, frame, pipelines, entry, target, sample, ready):
    image = frame("daily_gift", sample, REGIONS)
    frames = iter(([image] if entry != "DailyGift_SelectGate" else []) + [np.zeros_like(image)] * 3)
    native.controller.source = lambda: next(frames, image if ready else np.zeros_like(image))
    patch = overrides(pipelines, timeout=500)
    patch[target].update(action="DoNothing", next=[])
    names = [node.name for node in native.run(entry, patch).nodes]
    assert names[-1] == (target if ready else "Daily_Stop"), names
