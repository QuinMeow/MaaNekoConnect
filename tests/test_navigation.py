import numpy as np
import pytest


REGIONS = {
    "home_label": (530, 1205, 155, 65), "home_building": (535, 1105, 140, 110),
    "cafe_title": (0, 20, 160, 70), "enhance_icon": (610, 420, 85, 90),
    "enhance_title": (0, 20, 160, 70), "furniture_tab": (30, 1088, 215, 55),
    "footer_home": (280, 1195, 160, 75), "footer_back": (95, 1195, 115, 75),
    "date_message": (255, 515, 215, 40), "date_button": (211, 635, 298, 62),
    "reward_banner": (32, 97, 47, 52), "reward_panel": (0, 1150, 720, 34),
    "reward_blank": (280, 1200, 160, 55), "promo_continue": (240, 1204, 240, 27),
    "close": (310, 1135, 100, 100),
    "access_message": (126, 518, 457, 33),
    "device_title": (255, 296, 211, 33), "device_message": (62, 365, 596, 82),
    "device_ok": (211, 805, 298, 62),
    "network_message": (185, 508, 350, 54), "network_confirm": (211, 635, 298, 62),
    "login_title": (225, 295, 270, 40), "login_message": (195, 375, 330, 60),
    "mail_title": (180, 80, 360, 70), "mail_tab": (55, 1018, 230, 44),
    "capacity_header": (75, 188, 185, 45), "capacity_footer": (200, 905, 330, 55),
    "guild_help": (250, 75, 220, 65), "guild_donate": (235, 170, 250, 70),
    "reward": (298, 398, 128, 32),
    "page_title": (0, 20, 250, 80),
}
ARRIVALS = ("NavHome_Arrived", "NavSoleil_Arrived")
MOVES = ("NavSoleil_FromHome", "NavHome_FromSoleil", "NavHome_FromFurnitureEnhance")


def navigate(native, pipelines, images, route="NavHome_Ensure", persistent=False, popup_limit=20):
    clicks = []
    native.controller.image = images[0]

    def click(x, y):
        clicks.append((x, y))
        native.controller.image = images[0] if persistent else images[min(len(clicks), len(images) - 1)]
        return True

    native.controller.on_click = click
    native.controller.on_stop = native.controller.on_start = lambda package: True
    overrides = {name: {"post_delay": 0, "pre_delay": 0, "timeout": 30, "rate_limit": 1}
                 for name in pipelines}
    for name in ("CommonRecoveryBeforeRestart", "CommonRecoveryStopCapture"):
        overrides[name]["action"] = "DoNothing"
    overrides["NavHome_PopupPermit"]["max_hit"] = popup_limit
    overrides["NavFixture"] = {"recognition": "DirectHit", "post_delay": 0, "next": [route], "anchor": {
        "NavHome_Return": "NavDone", "NavSoleil_Return": "NavDone", "CommonRecoveryResume": "NavDone",
        "NavHome_PopupReturn": "NavHome_Normalize"}}
    overrides["NavDone"] = {"recognition": "DirectHit", "post_delay": 0, "next": []}
    if route in ("NavHome_FromSoleil", "NavHome_FromFurnitureEnhance"):
        overrides[route].update(recognition="DirectHit", action="DoNothing")
    return [node.name for node in native.run("NavFixture", overrides).nodes], clicks


@pytest.mark.parametrize("sample,expected", [
    ("home_ready", (ARRIVALS[0], MOVES[0])), ("home_holdout", (ARRIVALS[0], MOVES[0])),
    ("cafe", (ARRIVALS[1], MOVES[1])), ("enhance", (MOVES[2],)),
    ("home_loading", ()), ("transition_loading", ()),
])
def test_only_ready_supported_pages_allow_arrival_or_navigation(native, frame, sample, expected):
    image = frame("navigation", sample, REGIONS)
    for name in ARRIVALS + MOVES:
        assert native.match(name, image) is (name in expected), (sample, name)


@pytest.mark.parametrize("sample", ["home_ready", "cafe", "enhance"])
@pytest.mark.parametrize("factor", [0.5, 0.75])
def test_dimmed_page_cannot_authorize_navigation(native, frame, sample, factor):
    image = (frame("navigation", sample, REGIONS) * factor).astype(np.uint8)
    assert not any(native.match(name, image) for name in ARRIVALS + MOVES)


@pytest.mark.parametrize("sample,region,node", [
    ("home_ready", "home_label", "NavHome_Arrived"),
    ("home_ready", "home_building", "NavHome_Arrived"),
    ("cafe", "cafe_title", "NavSoleil_Arrived"),
    ("cafe", "enhance_icon", "NavSoleil_Arrived"),
    ("cafe", "footer_home", "NavHome_FromSoleil"),
    ("enhance", "footer_home", "NavHome_FromFurnitureEnhance"),
])
def test_navigation_needs_a_complete_page_and_its_button(native, frame, sample, region, node):
    image = frame("navigation", sample, REGIONS)
    x, y, width, height = REGIONS[region]
    image[y:y + height, x:x + width] = 0
    assert not native.match(node, image)


@pytest.mark.parametrize("value", [0, 128, 255])
def test_uniform_frames_are_not_navigation_permission(native, value):
    image = np.full((1280, 720, 3), value, dtype=np.uint8)
    assert not any(native.match(name, image) for name in ARRIVALS + MOVES)


def test_navigation_preserves_callers_recovery_and_never_spends(pipelines):
    for name, node in pipelines.items():
        if not name.startswith("Nav"):
            continue
        assert "CommonRecoveryResume" not in node.get("anchor", {})
        assert node.get("action") in (None, "Click")
        assert "custom_action" not in node and node.get("repeat", 1) == 1
    for place in ("Home", "Soleil"):
        assert pipelines[f"Nav{place}_Arrived"]["next"] == [f"[Anchor]Nav{place}_Return"]
    assert "CommonRecoveryHomeStallEnter" in pipelines["NavSoleil_FromHome"]["on_error"]


@pytest.mark.parametrize("sample,expected", [
    ("monthly_bonus", "NavHome_DismissReward"), ("event_bonus", "NavHome_DismissReward"),
    ("half_bonus", "NavHome_DismissReward"), ("event_promo", "NavHome_DismissPromo"),
    ("gacha_promo", "NavHome_DismissPromo"), ("notice_list", "NavHome_DismissClose"),
])
def test_popup_uses_shared_chrome_or_dismiss_control_not_campaign_text(native, frame, sample, expected):
    image = frame("navigation", sample, REGIONS)
    handlers = ("NavHome_DismissReward", "NavHome_DismissPromo", "NavHome_DismissClose")
    if sample == "notice_list":
        image[85:130, 280:440] = 0
        image[1024:1062, 85:197] = 0
    elif sample.endswith("promo"):
        image[1070:1100, 230:545] = 0
    for name in handlers:
        assert native.match(name, image) is (name == expected)
        assert not native.match(name, frame("navigation", "home_ready", REGIONS))
    assert not native.match(expected, (image * 0.75).astype(np.uint8))
    assert not native.match("NavHome_Arrived", image)
    regions = (("close",) if sample == "notice_list" else ("promo_continue",) if sample.endswith("promo") else
               ("reward_banner", "reward_panel", "reward_blank"))
    for region in regions:
        partial = image.copy()
        x, y, w, h = REGIONS[region]
        partial[y:y + h, x:x + w] = 0
        assert not native.match(expected, partial)


@pytest.mark.parametrize("route,samples", [
    ("NavHome_Ensure", ["monthly_bonus", "event_bonus", "half_bonus", "event_promo", "gacha_promo", "notice_list"]),
    ("NavHome_FromSoleil", ["event_promo", "notice_list"]),
    ("NavHome_FromFurnitureEnhance", ["notice_list"]),
    ("CommonRecoveryDispatch", ["monthly_bonus", "half_bonus", "notice_list"]),
])
def test_variable_popup_chain_returns_to_caller_without_spending(native, pipelines, frame, route, samples):
    samples = samples + ["home_ready"]
    images = [frame("navigation", sample, REGIONS) for sample in samples]
    names, clicks = navigate(native, pipelines, images, route)
    assert names[-1] == "NavDone" and len(clicks) == len(samples) - 1
    assert all(350 <= x <= 370 and 1170 <= y <= 1230 for x, y in clicks)
    assert names.count("NavHome_PopupPermit") == len(clicks)


def test_persistent_popup_stops_at_shared_budget(native, pipelines, frame):
    names, clicks = navigate(native, pipelines, [frame("navigation", "event_bonus", REGIONS)],
                             persistent=True, popup_limit=3)
    assert len(clicks) == 3 and 0 < pipelines["NavHome_PopupPermit"]["max_hit"] <= 20
    assert names[-1] == "CommonRecoveryStop"


@pytest.mark.parametrize("group,sample,node", [("navigation", "date_changed", "CommonDateChangedConfirm"),
                                            ("recovery", "access_denied", "CommonAccessDeniedConfirm"),
                                            ("recovery", "network_stable", "CommonNetworkConfirm"),
                                            ("recovery", "play_device", "CommonPlayDeviceConfirm"),
                                            ("recovery", "login_failed", "CommonLoginFailedConfirm")])
def test_known_title_return_error_wins_over_close_visible_underneath(native, pipelines, frame, group, sample, node):
    image = frame(group, sample, REGIONS)
    close = frame("navigation", "notice_list", REGIONS)
    image[1135:1235, 310:410] = close[1135:1235, 310:410]
    assert native.match("NavHome_DismissClose", image)
    names, clicks = navigate(native, pipelines, [image, frame("navigation", "home_ready", REGIONS)])
    assert names[-1] == "NavDone" and len(clicks) == 1
    assert node in names and "NavHome_DismissClose" not in names


@pytest.mark.parametrize("route", ["NavHome_Ensure", "NavSoleil_Ensure", "CommonRecoveryDispatch", "CommonRecoveryFreshCheck"])
@pytest.mark.parametrize("persistent", [False, True])
@pytest.mark.parametrize("sample", ["quest", "prep", "delivery"])
def test_known_non_home_returns_to_new_caller_once_without_restarting_static_page(native, pipelines, frame, route, persistent, sample):
    page = (frame("daily_gift", "quest", {"quest_title": (0, 20, 250, 80), "home": (280, 1195, 160, 75)})
            if sample == "quest" else frame("navigation", "normalize_" + sample, REGIONS))
    images = [page, frame("navigation", "home_ready", REGIONS)]
    if route == "NavSoleil_Ensure":
        images.append(frame("navigation", "cafe", REGIONS))
    names, clicks = navigate(native, pipelines, images, route, persistent)
    assert len(clicks) == (2 if route == "NavSoleil_Ensure" and not persistent else 1)
    assert names[-1] == ("CommonRecoveryStop" if persistent else "NavDone")
    assert not any(name.endswith("Spend") or name in ("CommonStopGame", "CommonStartGame") for name in names)


@pytest.mark.parametrize("sample", ["mail", "capacity", "guild_help", "guild_donate", "reward"])
@pytest.mark.parametrize("persistent", [False, True])
def test_known_modal_closes_only_via_shared_budget_not_its_previous_business(native, pipelines, frame, sample, persistent):
    modal = frame("navigation", "normalize_" + sample, REGIONS)
    names, clicks = navigate(native, pipelines, [modal, frame("navigation", "home_ready", REGIONS)],
                             persistent=persistent, popup_limit=3)
    assert len(clicks) == (3 if persistent else 1)
    assert names[-1] == ("CommonRecoveryStop" if persistent else "NavDone")
    assert names.count("NavHome_PopupPermit") == len(clicks)
    assert not any(name.startswith("Daily") or name.endswith("Spend") for name in names)
