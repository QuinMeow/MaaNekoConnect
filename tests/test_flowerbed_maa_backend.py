import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.flowerbed.action import StartOutcome
from agent.flowerbed.maa_backend import MaaFlowerbedBackend
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


def read_task(attribute, succeeded=True):
    return SimpleNamespace(
        status=status(succeeded),
        nodes=[
            node("SoleilFlowerbedReadTitle", TITLE_BY_ATTRIBUTE[attribute]),
            node("SoleilFlowerbedReadLevels", "Lv 1 ▶ 2"),
            node("SoleilFlowerbedReadBonuses", "+0.0 ▶ +1.0"),
            node("SoleilFlowerbedReadResources", "10,000 ▶ 9,999"),
            node("SoleilFlowerbedReadDuration", "100:00:00"),
            count_node("SoleilFlowerbedUpgradeButtonEnabled"),
            node("SoleilFlowerbedUpgradeButtonText", "強化"),
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
        "SoleilFlowerbedMainPageFoodLabel",
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
    courtyard = pipeline["SoleilFlowerbedOpenCourtyard"]
    garden = pipeline["SoleilFlowerbedOpenGarden"]

    assert courtyard["recognition"] == "OCR"
    assert courtyard["expected"] == "中庭"
    assert courtyard["next"] == ["SoleilFlowerbedOpenGarden"]
    assert garden["recognition"] == "OCR"
    assert garden["expected"] == "中庭"
    assert garden["action"] == "Click"
    assert garden["target"] == [360, 600]


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


def test_read_failure_closes_popup_before_state_detection_and_fails_closed():
    context = FakeContext(read_failure_attribute="Food")

    with pytest.raises(RuntimeError, match="could not be confirmed"):
        MaaFlowerbedBackend(context).scan()

    close_index = context.calls.index("SoleilFlowerbedClosePopup")
    active_index = context.calls.index("SoleilFlowerbedDetectActiveEntry")
    assert close_index < active_index
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
