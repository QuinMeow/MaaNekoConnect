import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.flowerbed.action import StartOutcome
from agent.flowerbed.maa_backend import MaaFlowerbedBackend, _ocr_text
from agent.flowerbed.models import Candidate
from agent.flowerbed.priority import ATTRIBUTE_ORDER, FLOWER_ORDER


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_PATH = (
    ROOT / "assets" / "resource" / "pipeline" / "soleil_flowerbed.json"
)


TITLE_BY_ATTRIBUTE = {
    "Food": "フード強化",
    "Sweets": "スイーツ強化",
    "Drink": "ドリンク強化",
    "Customer Service": "接客力強化",
    "Work Speed": "作業速度強化",
    "Stamina": "スタミナ強化",
}


OPEN_ENTRY_BY_ATTRIBUTE = {
    "Food": "SoleilFlowerbedOpenFood",
    "Sweets": "SoleilFlowerbedOpenSweets",
    "Drink": "SoleilFlowerbedOpenDrink",
    "Customer Service": "SoleilFlowerbedOpenCustomerService",
    "Work Speed": "SoleilFlowerbedOpenWorkSpeed",
    "Stamina": "SoleilFlowerbedOpenStamina",
}


def status(succeeded=True):
    return SimpleNamespace(succeeded=succeeded)


def recognition(text="", score=0.99, hit=True):
    result = SimpleNamespace(text=text, score=score)
    return SimpleNamespace(hit=hit, best_result=result if hit else None)


def node(name, text="", score=0.99, hit=True):
    return SimpleNamespace(
        name=name,
        completed=True,
        recognition=recognition(text, score, hit),
    )


def count_node(name, count=100, hit=True):
    result = SimpleNamespace(count=count)
    return SimpleNamespace(
        name=name,
        completed=True,
        recognition=SimpleNamespace(
            hit=hit,
            best_result=result if hit else None,
        ),
    )


def read_task(
    attribute,
    succeeded=True,
    enabled=True,
    current_level=1,
    resources="10,000 ▶ 9,999",
):
    button_nodes = (
        [
            count_node("SoleilFlowerbedUpgradeButtonEnabled"),
            node("SoleilFlowerbedUpgradeButtonText", "強化"),
        ]
        if enabled
        else [count_node("SoleilFlowerbedUpgradeButtonDisabled")]
    )
    return SimpleNamespace(
        status=status(succeeded),
        nodes=[
            node("SoleilFlowerbedReadTitle", TITLE_BY_ATTRIBUTE[attribute]),
            node(
                "SoleilFlowerbedReadLevels",
                f"Lv {current_level} ▶ {current_level + 1}",
            ),
            node("SoleilFlowerbedReadBonuses", "+0.0 ▶ +1.0"),
            node("SoleilFlowerbedReadResources", resources),
            node("SoleilFlowerbedReadDuration", "100:00:00"),
            *button_nodes,
        ],
    )


def recognition_task(name, hit):
    return SimpleNamespace(
        status=status(),
        nodes=[node(name, "matched", hit=hit)],
    )


class FakeContext:
    def __init__(
        self,
        *,
        read_failure_attribute=None,
        active_hit=False,
        capped_hit=False,
        confirm_started_hit=True,
    ):
        self.calls = []
        self.attribute = "Food"
        self.popup_open = False
        self.read_failure_attribute = read_failure_attribute
        self.active_hit = active_hit
        self.capped_hit = capped_hit
        self.confirm_started_hit = confirm_started_hit

    def run_task(self, entry):
        self.calls.append(entry)
        for attribute, open_entry in OPEN_ENTRY_BY_ATTRIBUTE.items():
            if entry == open_entry:
                self.attribute = attribute
                self.popup_open = True
                return SimpleNamespace(status=status(), nodes=[])
        if entry == "SoleilFlowerbedReadPopupEntry":
            return read_task(
                self.attribute,
                succeeded=self.attribute != self.read_failure_attribute,
            )
        if entry == "SoleilFlowerbedClosePopup":
            self.popup_open = False
            return SimpleNamespace(status=status(), nodes=[])
        if entry == "SoleilFlowerbedDetectActiveEntry":
            assert not self.popup_open
            return recognition_task(
                "SoleilFlowerbedDetectActive",
                self.active_hit,
            )
        if entry == "SoleilFlowerbedDetectCappedEntry":
            assert not self.popup_open
            return recognition_task(
                "SoleilFlowerbedDetectCapped",
                self.capped_hit,
            )
        if entry == "SoleilFlowerbedConfirmStartedEntry":
            return recognition_task(
                "SoleilFlowerbedConfirmStartedState",
                self.confirm_started_hit,
            )
        known_actions = {
            "SoleilFlowerbedResetFlowerList",
            "SoleilFlowerbedScrollToLastFlower",
            "SoleilFlowerbedSelectFlower0",
            "SoleilFlowerbedSelectFlower1",
            "SoleilFlowerbedSelectFlower2",
            "SoleilFlowerbedSelectFlower3",
            "SoleilFlowerbedSelectFlower4",
            "SoleilFlowerbedConfirmStart",
        }
        if entry in known_actions:
            return SimpleNamespace(status=status(), nodes=[])
        return SimpleNamespace(status=status(False), nodes=[])


def candidate():
    return Candidate(
        flower=FLOWER_ORDER[0],
        attribute=ATTRIBUTE_ORDER[0],
        current_level=1,
        next_level=2,
        current_bonus=0.0,
        next_bonus=1.0,
        cost=1,
        duration_seconds=360000,
        resource_balance=10000,
        active=False,
        button_enabled=True,
        capped=False,
        confidence=0.99,
    )


def test_pipeline_defines_wrapper_entries_for_every_recognition_flow():
    pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    wrappers = {
        "SoleilFlowerbedReadPopupEntry": "SoleilFlowerbedReadTitle",
        "SoleilFlowerbedDetectActiveEntry": "SoleilFlowerbedDetectActive",
        "SoleilFlowerbedDetectCappedEntry": "SoleilFlowerbedDetectCapped",
        "SoleilFlowerbedConfirmStartedEntry": "SoleilFlowerbedConfirmStartedState",
    }

    for wrapper, recognition_name in wrappers.items():
        assert wrapper in pipeline
        assert pipeline[wrapper]["next"] == [recognition_name]
        assert "recognition" not in pipeline[wrapper]
        assert "recognition" in pipeline[recognition_name]


def test_already_open_chain_uses_next_candidates_for_safe_navigation_fallback():
    pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))

    assert pipeline["SoleilFlowerbedAlreadyOpenEntry"]["next"] == [
        "SoleilFlowerbedMainPageFlowerName",
        "SoleilFlowerbedMainPageFoodLabel",
        "SoleilFlowerbedStoreHasCourtyardTab",
        "SoleilFlowerbedOpenSoleil",
    ]
    assert pipeline["SoleilFlowerbedMainPageFoodLabel"]["next"] == [
        "SoleilFlowerbedMainPageSweetsLabel",
        "SoleilFlowerbedOpenSoleil",
    ]
    assert pipeline["SoleilFlowerbedMainPageSweetsLabel"]["next"] == [
        "SoleilFlowerbedMainPageFlowerName",
        "SoleilFlowerbedOpenSoleil",
    ]
    for name in (
        "SoleilFlowerbedMainPageFoodLabel",
        "SoleilFlowerbedMainPageSweetsLabel",
        "SoleilFlowerbedMainPageFlowerName",
    ):
        assert "on_error" not in pipeline[name]


def test_courtyard_navigation_requires_recognition_before_each_click():
    pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))
    entry = pipeline["SoleilFlowerbedAlreadyOpenEntry"]
    store = pipeline["SoleilFlowerbedStoreHasCourtyardTab"]
    courtyard = pipeline["SoleilFlowerbedOpenCourtyard"]
    garden = pipeline["SoleilFlowerbedOpenGarden"]

    assert entry["next"] == [
        "SoleilFlowerbedMainPageFlowerName",
        "SoleilFlowerbedMainPageFoodLabel",
        "SoleilFlowerbedStoreHasCourtyardTab",
        "SoleilFlowerbedOpenSoleil",
    ]
    flower_name = pipeline["SoleilFlowerbedMainPageFlowerName"]
    assert flower_name["expected"] == ".+の花"
    assert flower_name["next"] == ["SoleilFlowerbedPlanAndExecute"]
    assert store["recognition"] == "OCR"
    assert store["model"] == "ja_jp"
    assert store["expected"] == "中庭"
    assert store["action"] == "Click"
    assert store["next"] == ["SoleilFlowerbedOpenGarden"]
    assert courtyard["recognition"] == "OCR"
    assert courtyard["expected"] == "中庭"
    assert courtyard["next"] == ["SoleilFlowerbedOpenGarden"]
    assert garden["recognition"] == "ColorMatch"
    assert garden["roi"] == [410, 1030, 90, 120]
    assert garden["count"] >= 100
    assert garden["action"] == "Click"
    assert garden["target"] == [360, 600]


def test_popup_reader_joins_all_ocr_fragments_in_screen_order():
    result = SimpleNamespace(
        text="3940",
        score=0.97,
        box=[258, 388, 281, 62],
    )
    recognition = SimpleNamespace(
        hit=True,
        best_result=result,
        all_results=[
            SimpleNamespace(text="40", score=0.98, box=[400, 387, 30, 62]),
            SimpleNamespace(text="39", score=0.97, box=[258, 388, 30, 62]),
        ],
    )
    node = SimpleNamespace(name="SoleilFlowerbedReadLevels", recognition=recognition)

    assert _ocr_text(node) == "39 40"


def test_disabled_upgrade_button_is_a_confirmed_stage_cap():
    context = SimpleNamespace(
            run_task=lambda entry: read_task(
                attribute="Customer Service",
                enabled=False,
                current_level=50,
            )
    )
    backend = MaaFlowerbedBackend(context)

    with pytest.raises(ValueError, match="capped"):
        backend._read_open_popup("始まりの花", "Customer Service")


def test_non_cap_disabled_button_fails_closed():
    context = SimpleNamespace(
        run_task=lambda entry: read_task(
            attribute="Food",
            enabled=False,
        )
    )
    backend = MaaFlowerbedBackend(context)

    with pytest.raises(RuntimeError, match="could not be confirmed"):
        backend._read_open_popup("始まりの花", "Food")


def test_disabled_button_with_proven_resource_shortage_is_unavailable():
    context = SimpleNamespace(
        run_task=lambda entry: read_task(
            attribute="Food",
            enabled=False,
            resources="347 ▶ -1,333",
        )
    )
    backend = MaaFlowerbedBackend(context)

    with pytest.raises(ValueError, match="unavailable"):
        backend._read_open_popup("輝きの花", "Food")


def test_duration_can_branch_to_enabled_or_disabled_button_state():
    pipeline = json.loads(PIPELINE_PATH.read_text(encoding="utf-8"))

    assert pipeline["SoleilFlowerbedReadLevels"]["expected"] == "\\d+"
    assert pipeline["SoleilFlowerbedReadDuration"]["next"] == [
        "SoleilFlowerbedUpgradeButtonEnabled",
        "SoleilFlowerbedUpgradeButtonDisabled",
    ]
    disabled = pipeline["SoleilFlowerbedUpgradeButtonDisabled"]
    assert disabled["recognition"] == "ColorMatch"
    assert disabled["roi"] == [210, 780, 300, 80]
    assert disabled["count"] >= 100
    enabled = pipeline["SoleilFlowerbedUpgradeButtonEnabled"]
    assert any(
        disabled["lower"][channel] > enabled["upper"][channel]
        or enabled["lower"][channel] > disabled["upper"][channel]
        for channel in range(3)
    )


def test_backend_calls_wrapper_entries_instead_of_recognition_nodes():
    context = FakeContext()
    backend = MaaFlowerbedBackend(context)
    proposed = candidate()

    assert backend.verify(proposed) == proposed
    assert backend.start(proposed) is StartOutcome.CONFIRMED
    assert "SoleilFlowerbedReadPopupEntry" in context.calls
    assert "SoleilFlowerbedReadTitle" not in context.calls
    assert "SoleilFlowerbedConfirmStartedEntry" in context.calls
    assert "SoleilFlowerbedConfirmStartedState" not in context.calls


def test_backend_scans_all_five_flowers_and_six_attributes():
    context = FakeContext()

    snapshot = MaaFlowerbedBackend(context).scan()

    assert snapshot.active_count == 0
    assert len(snapshot.candidates) == 30
    assert {item.flower for item in snapshot.candidates} == set(FLOWER_ORDER)
    assert {item.attribute for item in snapshot.candidates} == set(ATTRIBUTE_ORDER)
    assert "SoleilFlowerbedScrollToLastFlower" in context.calls
    assert "SoleilFlowerbedConfirmStart" not in context.calls


def test_read_failure_closes_popup_without_guessing_unavailable_state():
    context = FakeContext(read_failure_attribute="Food")

    with pytest.raises(RuntimeError, match="pipeline subflow failed"):
        MaaFlowerbedBackend(context).scan()

    assert "SoleilFlowerbedClosePopup" in context.calls
    assert "SoleilFlowerbedDetectActiveEntry" not in context.calls
    assert "SoleilFlowerbedDetectCappedEntry" not in context.calls
    assert context.popup_open is False


def test_scan_best_effort_closes_popup_when_popup_parsing_raises():
    context = FakeContext(read_failure_attribute="Food")

    with pytest.raises(RuntimeError):
        MaaFlowerbedBackend(context).scan()

    assert context.calls.count("SoleilFlowerbedClosePopup") >= 1
    assert context.popup_open is False


def test_backend_verifies_popup_then_confirms_exactly_one_start():
    context = FakeContext()
    backend = MaaFlowerbedBackend(context)
    proposed = candidate()

    assert backend.verify(proposed) == proposed
    assert backend.start(proposed) is StartOutcome.CONFIRMED
    assert context.calls.count("SoleilFlowerbedConfirmStart") == 1
    assert context.calls[-1] == "SoleilFlowerbedConfirmStartedEntry"


def test_confirm_started_requires_recognition_hit_not_task_success():
    context = FakeContext(confirm_started_hit=False)
    backend = MaaFlowerbedBackend(context)
    proposed = candidate()

    assert backend.verify(proposed) == proposed
    assert backend.start(proposed) is StartOutcome.UNKNOWN


def test_extension_registers_the_pipeline_custom_action_name():
    source = (ROOT / "agent" / "extensions.py").read_text(encoding="utf-8")

    assert '"SoleilFlowerbedAuto"' in source
    assert "SoleilFlowerbedAutoAction" in source
