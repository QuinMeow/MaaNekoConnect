import pytest


@pytest.mark.parametrize("upgradeable,placed", [(False, False), (False, True), (True, False), (True, True)])
def test_filters_change_only_when_current_state_differs_from_requested_state(
    native, soleil_image, pipelines, upgradeable, placed,
):
    image = soleil_image("filters_both_checked")
    unchecked = soleil_image("filters_reset")
    for checked, y in ((upgradeable, 635), (placed, 780)):
        if not checked:
            image[y:y + 42, 88:128] = unchecked[y:y + 42, 88:128]
    assert native.match("FurnitureFilter_ApplyLevel", image)
    for prefix, checked in (("Upgradeable", upgradeable), ("Placed", placed)):
        for desired in (False, True):
            mode = "On" if desired else "Off"
            candidates = pipelines[f"FurnitureFilter_{prefix}{mode}"]["next"]
            matched = next(name for name in candidates if native.match(name, image))
            if checked == desired:
                assert pipelines[matched].get("action", "DoNothing") == "DoNothing"
            else:
                assert pipelines[matched]["action"] == "Click"
                operation = "Enable" if desired else "Disable"
                assert matched == f"FurnitureFilter_{operation}{prefix}"


@pytest.mark.parametrize("sample", ["idle_slot1", "active_slot1", "home_ready", "network_error"])
def test_unrelated_pages_cannot_change_filters(native, soleil_image, sample):
    image = soleil_image(sample)
    for prefix in ("Upgradeable", "Placed"):
        for operation in ("Enable", "Disable"):
            assert not native.match(f"FurnitureFilter_{operation}{prefix}", image)
