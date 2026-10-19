import numpy as np
import pytest


REGIONS = {
    "home_label": (530, 1205, 155, 65), "home_building": (535, 1105, 140, 110),
    "cafe_title": (0, 20, 160, 70), "enhance_icon": (610, 420, 85, 90),
    "enhance_title": (0, 20, 160, 70), "furniture_tab": (30, 1088, 215, 55),
    "footer_home": (280, 1195, 160, 75), "footer_back": (95, 1195, 115, 75),
}
ARRIVALS = ("NavHome_Arrived", "NavSoleil_Arrived")
MOVES = ("NavSoleil_FromHome", "NavHome_FromSoleil", "NavHome_FromFurnitureEnhance")


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
        if node.get("action") == "Click":
            assert name in MOVES
    for place in ("Home", "Soleil"):
        assert pipelines[f"Nav{place}_Arrived"]["next"] == [f"[Anchor]Nav{place}_Return"]
    assert "CommonRecoveryHomeStallEnter" in pipelines["NavSoleil_FromHome"]["on_error"]
