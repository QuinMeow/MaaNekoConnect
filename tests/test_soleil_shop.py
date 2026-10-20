import pytest


@pytest.mark.parametrize("sample,expected", [
    ("room_request", True), ("idle_slot1", False), ("active_slot1", False),
    ("filters_both_checked", False), ("home_ready", False), ("network_error", False),
])
def test_request_needs_the_shop_page_and_request_button(native, soleil_image, sample, expected):
    assert native.match("Soleil_RequestSupport", soleil_image(sample)) is expected


@pytest.mark.parametrize("roi", [(0, 20, 160, 70), (610, 630, 85, 90)])
def test_partial_shop_page_cannot_request(native, soleil_image, roi):
    image = soleil_image("room_request")
    x, y, width, height = roi
    image[y:y + height, x:x + width] = 0
    assert not native.match("Soleil_RequestSupport", image)


def test_request_permission_is_consumed_before_a_single_click(pipelines):
    prepare = pipelines["Soleil_RequestPrepare"]
    for anchor in ("CommonRecoveryResume", "FurnitureEnhance_PostRound"):
        assert prepare["anchor"][anchor] == "FurnitureEnhance_RoundComplete"
    request = pipelines["Soleil_RequestSupport"]
    assert request["action"] == "Click" and request.get("repeat", 1) == 1
