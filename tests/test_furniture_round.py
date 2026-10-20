import pytest
from maa.custom_recognition import CustomRecognition


@pytest.mark.parametrize("available,cap,auto_request,fail_start,fail_request,attempts,acks,requests", [
    (0, 99, True, False, False, 0, 0, []),
    (1, 99, True, False, False, 1, 1, [1]),
    (3, 99, True, False, False, 3, 3, [3]),
    (5, 99, True, False, False, 5, 5, [5]),
    (99, 99, True, False, False, 5, 5, [5]),
    (99, 99, False, False, False, 5, 5, []),
    (99, 99, True, True, False, 5, 4, [5]),
    (99, 2, True, False, False, 2, 2, [2]),
    (99, 99, True, False, True, 5, 5, [5]),
])
def test_round_is_bounded_and_never_refunds_attempts_or_replays_requests(
    native, pipelines, available, cap, auto_request, fail_start, fail_request, attempts, acks, requests,
):
    observed = {"attempts": 0, "requests": []}

    class Candidate(CustomRecognition):
        def analyze(self, context, argv):
            return (0, 0, 1, 1) if observed["attempts"] < available else None

    def click(x, y):
        if 345 <= x <= 375 and 1025 <= y <= 1040:
            observed["attempts"] += 1
            return not (fail_start and observed["attempts"] == 1)
        if 635 <= x <= 660 and 660 <= y <= 685:
            observed["requests"].append(observed["attempts"])
            return not fail_request
        assert (90 <= x <= 110 and 485 <= y <= 505) or (140 <= x <= 160 and 1220 <= y <= 1240)
        return True

    native.controller.on_click = click
    assert native.resource.register_custom_recognition("RoundCandidate", Candidate())
    overrides = {name: {"recognition": "DirectHit", "pre_delay": 0, "post_delay": 0,
                        "timeout": 50, "rate_limit": 1} for name in pipelines}
    for slot in range(1, 6):
        for prefix in ("Busy", "Select"):
            overrides[f"FurnitureEnhance_{prefix}{slot}"].update({
                "recognition": "ColorMatch", "method": 4, "roi": [0, 0, 1, 1],
                "lower": [1, 1, 1], "upper": [2, 2, 2], "count": 1,
            })
    overrides["FurnitureEnhance_Select1"].update({
        "recognition": "Custom", "custom_recognition": "RoundCandidate",
        "next": ["FurnitureEnhance_Ready1"],
    })
    overrides["FurnitureEnhance_EnsurePage"]["next"] = ["FurnitureEnhance_Prepare"]
    overrides["FurnitureEnhance_Prepare"]["next"] = ["FurnitureEnhance_Scan"]
    overrides["FurnitureEnhance_SessionSpendPermit"]["max_hit"] = cap
    for name in ("FurnitureEnhance_Complete", "FurnitureSchedule_Complete"):
        overrides[name]["action"] = "DoNothing"
    overrides["CommonRecoveryEnter"]["next"] = ["[Anchor]CommonRecoveryResume"]
    if not auto_request:
        overrides["FurnitureEnhance_AfterStart"]["anchor"] = {
            "FurnitureEnhance_PostRound": "FurnitureEnhance_RoundComplete",
        }
    names = [node.name for node in native.run("FurnitureEnhance_Round", overrides).nodes]
    assert observed == {"attempts": attempts, "requests": requests}
    assert names.count("FurnitureEnhance_Started") == acks
    assert names.count("FurnitureEnhance_BeginRound") == 1
    assert names[-1] in ("FurnitureEnhance_Complete", "FurnitureSchedule_Complete")


@pytest.mark.parametrize("sample,selected", [("idle_slot1", 1), ("idle_slot2", 2), ("idle_slot5", 5)])
def test_only_the_selected_idle_slot_can_spend(native, soleil_image, sample, selected):
    image = soleil_image(sample)
    for slot in range(1, 6):
        assert native.match(f"FurnitureEnhance_Start{slot}", image) is (slot == selected)


@pytest.mark.parametrize("sample", ["active_slot1", "five_active", "network_error", "filters_both_checked"])
def test_busy_or_obscured_pages_never_spend(native, soleil_image, sample):
    image = soleil_image(sample)
    for slot in range(1, 6):
        assert not native.match(f"FurnitureEnhance_Start{slot}", image)


@pytest.mark.parametrize("roi", [
    (0, 20, 160, 70), (30, 1088, 215, 55), (685, 433, 16, 39),
    (230, 998, 260, 70), (37, 470, 3, 40), (133, 445, 23, 23),
])
def test_partial_page_cannot_authorize_spending(native, soleil_image, roi):
    image = soleil_image("idle_slot1")
    x, y, width, height = roi
    image[y:y + height, x:x + width] = 0
    assert not native.match("FurnitureEnhance_Start1", image)


@pytest.mark.parametrize("busy_mask", range(32))
def test_busy_markers_take_priority_over_eligibility(native, soleil_image, pipelines, busy_mask):
    image = soleil_image("idle_slot1")
    running = soleil_image("partial_complete")
    targets = pipelines["FurnitureEnhance_Scan"]["next"]
    for slot in range(1, 6):
        busy, select = f"FurnitureEnhance_Busy{slot}", f"FurnitureEnhance_Select{slot}"
        x = 65 + (slot - 1) * 130
        if busy_mask & (1 << (slot - 1)):
            image[460:525, x:x + 70] = running[460:525, 65:135]
        assert native.match(busy, image) is bool(busy_mask & (1 << (slot - 1)))
        assert targets.index(busy) < targets.index(select)


def test_ack_survives_grid_reordering(native, soleil_image):
    image = soleil_image("active_slot1")
    image[460:525, 65:135] = 0
    assert native.match("FurnitureEnhance_Started", image)
