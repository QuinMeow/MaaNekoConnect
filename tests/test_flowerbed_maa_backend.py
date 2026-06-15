from pathlib import Path
from types import SimpleNamespace

from agent.flowerbed.maa_backend import MaaFlowerbedBackend
from agent.flowerbed.models import Candidate
from agent.flowerbed.action import StartOutcome
from agent.flowerbed.priority import ATTRIBUTE_ORDER, FLOWER_ORDER


ROOT = Path(__file__).resolve().parents[1]


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


def read_task(attribute):
    return SimpleNamespace(
        status=status(),
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


class FakeContext:
    def __init__(self, confirm_started=True):
        self.calls = []
        self.attribute = "Food"
        self.confirm_started = confirm_started

    def run_task(self, entry):
        self.calls.append(entry)
        for attribute, open_entry in OPEN_ENTRY_BY_ATTRIBUTE.items():
            if entry == open_entry:
                self.attribute = attribute
                return SimpleNamespace(status=status(), nodes=[])
        if entry == "SoleilFlowerbedReadTitle":
            return read_task(self.attribute)
        if entry == "SoleilFlowerbedConfirmStartedState":
            return SimpleNamespace(
                status=status(self.confirm_started),
                nodes=[],
            )
        return SimpleNamespace(status=status(), nodes=[])


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


def test_backend_scans_all_five_flowers_and_six_attributes():
    context = FakeContext()

    snapshot = MaaFlowerbedBackend(context).scan()

    assert snapshot.active_count == 0
    assert len(snapshot.candidates) == 30
    assert {item.flower for item in snapshot.candidates} == set(FLOWER_ORDER)
    assert {item.attribute for item in snapshot.candidates} == set(ATTRIBUTE_ORDER)
    assert "SoleilFlowerbedScrollToLastFlower" in context.calls
    assert "SoleilFlowerbedConfirmStart" not in context.calls


def test_backend_verifies_popup_then_confirms_exactly_one_start():
    context = FakeContext()
    backend = MaaFlowerbedBackend(context)
    proposed = candidate()

    assert backend.verify(proposed) == proposed
    assert backend.start(proposed) is StartOutcome.CONFIRMED
    assert context.calls.count("SoleilFlowerbedConfirmStart") == 1
    assert context.calls[-1] == "SoleilFlowerbedConfirmStartedState"


def test_backend_reports_unknown_when_started_state_cannot_be_confirmed():
    context = FakeContext(confirm_started=False)
    backend = MaaFlowerbedBackend(context)
    proposed = candidate()

    assert backend.verify(proposed) == proposed
    assert backend.start(proposed) is StartOutcome.UNKNOWN


def test_extension_registers_the_pipeline_custom_action_name():
    source = (ROOT / "agent" / "extensions.py").read_text(encoding="utf-8")

    assert '"SoleilFlowerbedAuto"' in source
    assert "SoleilFlowerbedAutoAction" in source
