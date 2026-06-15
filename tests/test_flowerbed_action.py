from dataclasses import replace

from agent.flowerbed.action import (
    AutomationConfig,
    ExecutionMode,
    RunStatus,
    StartOutcome,
    run_automation,
)
from agent.flowerbed.models import Candidate, ScanSnapshot
from agent.flowerbed.priority import RatingWeights


def candidate(**changes):
    values = {
        "flower": "始まりの花",
        "attribute": "Food",
        "current_level": 1,
        "next_level": 2,
        "current_bonus": 0.0,
        "next_bonus": 1.0,
        "cost": 1,
        "duration_seconds": 60,
        "resource_balance": 100,
        "active": False,
        "button_enabled": True,
        "capped": False,
        "confidence": 0.99,
    }
    values.update(changes)
    return Candidate(**values)


def config(mode=ExecutionMode.PLAN_ONLY, max_starts=6):
    return AutomationConfig(
        execution_mode=mode,
        deadline_seconds=24 * 3600,
        max_starts=max_starts,
        allow_tail_fill=False,
        reserves={},
        weights=RatingWeights(),
    )


class FakeBackend:
    def __init__(self, snapshots, verified=None, outcomes=None):
        self.snapshots = list(snapshots)
        self.verified = list(verified or [])
        self.outcomes = list(outcomes or [])
        self.calls = []

    def scan(self):
        self.calls.append(("scan", None))
        if self.snapshots:
            return self.snapshots.pop(0)
        return ScanSnapshot(active_count=0, candidates=())

    def verify(self, proposed):
        self.calls.append(("verify", proposed.idempotency_key))
        if self.verified:
            return self.verified.pop(0)
        return proposed

    def start(self, proposed):
        self.calls.append(("start", proposed.idempotency_key))
        if self.outcomes:
            return self.outcomes.pop(0)
        return StartOutcome.CONFIRMED


def test_plan_only_scans_and_plans_without_verifying_or_starting():
    upgrade = candidate()
    backend = FakeBackend([ScanSnapshot(0, (upgrade,))])

    result = run_automation(config(), backend)

    assert result.status is RunStatus.PLANNED
    assert [item.candidate for item in result.planned] == [upgrade]
    assert result.started == ()
    assert backend.calls == [("scan", None)]


def test_execute_starts_only_one_candidate_before_rescanning():
    first = candidate(attribute="Customer Service")
    second = candidate(attribute="Food")
    backend = FakeBackend(
        [
            ScanSnapshot(0, (first, second)),
            ScanSnapshot(1, (second,)),
            ScanSnapshot(2, ()),
        ],
        outcomes=[StartOutcome.CONFIRMED, StartOutcome.CONFIRMED],
    )

    result = run_automation(config(ExecutionMode.EXECUTE), backend)

    assert result.status is RunStatus.COMPLETED
    assert result.started == (first, second)
    assert backend.calls == [
        ("scan", None),
        ("verify", first.idempotency_key),
        ("start", first.idempotency_key),
        ("scan", None),
        ("verify", second.idempotency_key),
        ("start", second.idempotency_key),
        ("scan", None),
    ]


def test_execute_stops_when_candidate_changes_before_start():
    proposed = candidate()
    changed = replace(proposed, next_bonus=1.5)
    backend = FakeBackend(
        [ScanSnapshot(0, (proposed,))],
        verified=[changed],
    )

    result = run_automation(config(ExecutionMode.EXECUTE), backend)

    assert result.status is RunStatus.STOPPED
    assert result.stop_reason == "candidate_changed_before_start"
    assert result.started == ()
    assert not any(call[0] == "start" for call in backend.calls)


def test_execute_stops_when_start_result_is_unknown():
    upgrade = candidate()
    backend = FakeBackend(
        [ScanSnapshot(0, (upgrade,))],
        outcomes=[StartOutcome.UNKNOWN],
    )

    result = run_automation(config(ExecutionMode.EXECUTE), backend)

    assert result.status is RunStatus.STOPPED
    assert result.stop_reason == "start_result_unknown"
    assert result.started == ()


def test_execute_stops_when_start_explicitly_fails():
    upgrade = candidate()
    backend = FakeBackend(
        [ScanSnapshot(0, (upgrade,))],
        outcomes=[StartOutcome.FAILED],
    )

    result = run_automation(config(ExecutionMode.EXECUTE), backend)

    assert result.status is RunStatus.STOPPED
    assert result.stop_reason == "start_failed"


def test_confirmed_idempotency_key_is_not_started_twice():
    upgrade = candidate()
    backend = FakeBackend(
        [
            ScanSnapshot(0, (upgrade,)),
            ScanSnapshot(1, (upgrade,)),
        ],
        outcomes=[StartOutcome.CONFIRMED],
    )

    result = run_automation(config(ExecutionMode.EXECUTE), backend)

    assert result.status is RunStatus.COMPLETED
    assert result.started == (upgrade,)
    assert [call[0] for call in backend.calls].count("start") == 1


def test_max_starts_caps_execute_even_when_slots_remain():
    first = candidate(attribute="Customer Service")
    second = candidate(attribute="Food")
    backend = FakeBackend(
        [
            ScanSnapshot(0, (first, second)),
            ScanSnapshot(1, (second,)),
        ]
    )

    result = run_automation(
        config(ExecutionMode.EXECUTE, max_starts=1),
        backend,
    )

    assert result.started == (first,)
    assert [call[0] for call in backend.calls].count("scan") == 1
