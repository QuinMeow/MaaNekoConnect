import json
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    "Login": "login",
    "Income": "income", "Friend": "friend", "Delivery": "delivery", "Gift": "gift",
    "VR": "vr", "Contest": "contest", "Exchange": "exchange", "Gacha": "gacha",
    "Mail": "mail", "Guild": "guild", "Rewards": "rewards",
}
FOREIGN = dict(zip(MODULES, ("gacha", "vr", "quest", "gift", "contest", "exchange",
                            "map", "guild", "members", "menu", "friend", "mission")))


def test_interface_options_are_reachable_without_retired_daily_switches():
    interface = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))
    assert interface["task"][-1]["entry"] == "DailyRewards_Start"
    entries = {task["entry"] for task in interface["task"] if task["entry"].startswith("Daily")}
    assert entries == {f"Daily{key}_Start" for key in MODULES}
    options, reachable = interface["option"], set()
    pending = [name for task in interface["task"] for name in task.get("option", [])]
    while pending:
        name = pending.pop()
        assert name in options, f"Dangling option reference: {name}"
        if name in reachable:
            continue
        reachable.add(name)
        pending.extend(options[name].get("option", []))
        pending.extend(child for case in options[name].get("cases", []) for child in case.get("option", []))
    assert set(options) == reachable, f"Unused options: {set(options) - reachable}"
    assert {name for name in options if name.startswith("Daily")} == {"DailyMilestones", "DailyGuildGoldDonation"}


@pytest.mark.parametrize("key", MODULES)
def test_recovery_returns_to_real_home_without_replaying_selected_work(native, pipelines, key):
    patch = fast(pipelines)
    patch[f"Daily{key}_Start"]["next"] = ["DailyCore_Recover"]
    native.controller.image = pages()["home"]
    names = [item.name for item in native.run(f"Daily{key}_Start", patch).nodes]
    assert names[-1] == "DailyCore_Done" and "NavHome_Normalized" in names
    assert not any(name.endswith("Spend") or name in ("Daily_Claim", "Daily_MilestoneClaim") for name in names)


def put(group, sample, positions, base=None):
    image = np.zeros((1280, 720, 3), dtype=np.uint8) if base is None else base.copy()
    with np.load(ROOT / "tests/fixtures" / group / f"{sample}.npz", allow_pickle=False) as crops:
        for key, (x, y) in positions.items():
            crop = crops[key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return image


def pages():
    footer = put("navigation", "cafe", {"footer_home": (280, 1195)})
    controls = {"vr": ("vr_title", (51, 42)), "contest": ("contest_title", (53, 42)),
                "exchange": ("exchange_title", (53, 42)), "gacha": ("gacha_title", (54, 42)),
                "map": ("map_title", (52, 43))}
    result = {name: put("daily", "controls", {key: pos}, footer) for name, (key, pos) in controls.items()}
    result["quest"] = put("daily_gift", "quest", {"quest_title": (0, 20), "home": (280, 1195)})
    result["gift"] = put("daily_gift", "zero", {
        "title": (35, 25), "quota": (254, 116), "tab": (30, 1090), "home": (280, 1195)})
    result["guild"] = put("daily", "guild_ready", {"guild_title": (45, 35), "footer_home": (280, 1195)})
    result["members"] = put("daily", "guild_members", {
        "members_title": (45, 35), "footer_home": (280, 1195)})
    close = put("recovery", "play_device", {"close": (310, 1135)})
    result["menu"] = put("daily", "controls", {"menu": (18, 448)}, close)
    result["friend"] = put("daily", "friend_batch", {"title": (284, 87), "tab": (81, 1022)}, close)
    result["mission"] = put("daily", "controls", {"header": (271, 117), "tab": (45, 1018)}, close)
    home = put("recovery", "home_ready_holdout", {
        "home_building": (535, 1105), "home_text": (530, 1205)})
    result["home"] = put("daily", "controls", {"sales_bubble": (443, 1040)}, home)
    result["footer"] = footer
    return result


def fast(pipelines):
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 60, "rate_limit": 1} for name in pipelines}
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    patch["CommonRecoveryStopCapture"]["action"] = "DoNothing"
    return patch


def selected(pipelines, key):
    anchor = pipelines[f"Daily{key}_Start"]["anchor"]
    return anchor.get("DailyCore_QuestTarget", anchor["NavHome_Return"])


@pytest.mark.parametrize("reverse", [False, True])
def test_all_selected_entries_normalize_foreign_pages_in_any_order_on_the_same_tasker(
    native, pipelines, reverse,
):
    images, patch = pages(), fast(pipelines)
    targets = {key: selected(pipelines, key) for key in MODULES}
    patch["CoreTestSelected"] = {"recognition": "DirectHit", "post_delay": 0, "next": []}
    for target in targets.values():
        if target != "DailyCore_Done":
            patch[target].update(action="DoNothing", next=["CoreTestSelected"])
    order = list(reversed(MODULES)) if reverse else list(MODULES)
    for key in order:
        native.controller.image = images[FOREIGN[key]]
        pending = [images["home"]] + ([images["quest"]] if key in ("VR", "Gift", "Contest") else [])
        clicks = []
        def click(x, y):
            clicks.append((x, y))
            native.controller.image = pending.pop(0)
            return True
        native.controller.on_click = click
        names = [node.name for node in native.run(f"Daily{key}_Start", patch).nodes]
        assert "NavHome_Normalized" in names and targets[key] in names, (key, names)
        assert names[-1] == ("DailyCore_Done" if key == "Login" else "CoreTestSelected")
        assert not pending and len(clicks) == (2 if key in ("VR", "Gift", "Contest") else 1)
        assert not set(names).intersection(set(targets.values()) - {targets[key]})
        assert not any(name.endswith("Spend") or name in ("Daily_Claim", "Daily_MilestoneClaim") for name in names)


@pytest.mark.parametrize("kind", ["unknown", "dim", "footer", "stuck"])
def test_unknown_dimmed_or_unresponsive_start_cannot_click_repeatedly_or_spend(native, pipelines, kind):
    images = pages()
    image = images["quest"]
    if kind == "unknown":
        image = np.full_like(image, 32)
    elif kind == "dim":
        image = (image * 0.65).astype(np.uint8)
    elif kind == "footer":
        image = images["footer"]
    native.controller.image = image
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    names = [node.name for node in native.run("DailyExchange_Start", fast(pipelines)).nodes]
    assert len(clicks) == (1 if kind == "stuck" else 0)
    assert names[-1] in ("CommonRecoveryStop", "Daily_Stop"), names
    assert "DailyExchange_MenuOpen" not in names and "DailyCore_Done" not in names
    assert not any(name.endswith("Spend") or name in ("CommonStopGame", "CommonStartGame") for name in names)


def test_return_home_stall_cannot_loop_clicks(native, pipelines):
    patch = fast(pipelines)
    patch["CoreTestReturn"] = {"recognition": "DirectHit", "post_delay": 0,
                               "anchor": {"Daily_AfterWork": "DailyCore_Done"}, "next": ["Daily_Return"]}
    native.controller.image = pages()["vr"]
    clicks = []
    native.controller.on_click = lambda x, y: clicks.append((x, y)) or True
    names = [node.name for node in native.run("CoreTestReturn", patch).nodes]
    assert len(clicks) == 1 and names[-1] in ("CommonRecoveryStop", "Daily_Stop")
    assert "DailyCore_Done" not in names and not any(name.endswith("Spend") for name in names)


def test_return_after_another_task_cannot_inherit_its_entry_business_caller(native, pipelines):
    images, patch = pages(), fast(pipelines)
    patch["Daily_FriendBegin"].update(action="DoNothing", next=["CoreEntrySeen"])
    patch["CoreEntrySeen"] = {"recognition": "DirectHit", "post_delay": 0, "next": []}
    native.controller.image = images["home"]
    first = [node.name for node in native.run("DailyFriend_Start", patch).nodes]
    assert first[-1] == "CoreEntrySeen"
    patch["CoreTestReturn"] = {"recognition": "DirectHit", "post_delay": 0,
                               "anchor": {"Daily_AfterWork": "DailyCore_Done"}, "next": ["Daily_Return"]}
    native.controller.image = images["quest"]
    clicks = []
    def click(x, y):
        clicks.append((x, y))
        native.controller.image = images["home"]
        return True
    native.controller.on_click = click
    second = [node.name for node in native.run("CoreTestReturn", patch).nodes]
    assert len(clicks) == 1 and second[-1] == "DailyCore_Done"
    assert "Daily_FriendBegin" not in second and "NavHome_Arrived" not in second


@pytest.mark.parametrize("source,ending", [("quest", "cafe"), ("map", "enhance")])
def test_furniture_schedule_and_following_daily_share_only_navigation(native, pipelines, source, ending):
    images, patch = pages(), fast(pipelines)
    cafe = put("navigation", "cafe", {"cafe_title": (0, 20), "enhance_icon": (610, 420),
                                      "footer_home": (280, 1195)})
    finish = cafe if ending == "cafe" else put("navigation", "enhance", {
        "enhance_title": (0, 20), "furniture_tab": (30, 1088), "footer_home": (280, 1195)})
    for name in ("FurnitureTimer_Config", "FurnitureTimer_IntervalConfig"):
        patch[name]["action"] = "DoNothing"
    patch["FurnitureEnhance_Open"].update(action="DoNothing", next=["FurnitureSchedule_Complete"])
    for entry, start, pending, terminal in (
        ("FurnitureSchedule_Start", images[source], [images["home"], cafe], "FurnitureSchedule_Complete"),
        ("DailyLogin_Start", finish, [images["home"]], "DailyCore_Done"),
    ):
        native.controller.image = start
        def click(x, y):
            native.controller.image = pending.pop(0)
            return True
        native.controller.on_click = click
        names = [node.name for node in native.run(entry, patch).nodes]
        assert names[-1] == terminal and not pending
        if entry == "FurnitureSchedule_Start":
            assert {"FurnitureSchedule_Permit", "NavSoleil_FromHome", "FurnitureEnhance_Open"} <= set(names)
        else:
            assert "NavHome_Normalized" in names and "FurnitureEnhance_Open" not in names
            assert "NavSoleil_FromHome" not in names
        assert "FurnitureEnhance_SessionSpendPermit" not in names
        assert not any(name.endswith("Spend") or name in ("Daily_Claim", "Daily_MilestoneClaim") for name in names)
