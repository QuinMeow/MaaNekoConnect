from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Protocol

from .models import Candidate, ScanSnapshot
from .priority import (
    FLOWER_ORDER,
    PlanItem,
    RatingWeights,
    ScheduleConfig,
    select_candidates,
)


class ExecutionMode(str, Enum):
    PLAN_ONLY = "PlanOnly"
    EXECUTE = "Execute"


class StartOutcome(str, Enum):
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class RunStatus(str, Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class AutomationConfig:
    execution_mode: ExecutionMode
    deadline_seconds: int
    max_starts: int
    allow_tail_fill: bool
    reserves: Mapping[str, int]
    weights: RatingWeights

    def schedule_config(self, max_starts: int | None = None) -> ScheduleConfig:
        return ScheduleConfig(
            deadline_seconds=self.deadline_seconds,
            max_starts=self.max_starts if max_starts is None else max_starts,
            allow_tail_fill=self.allow_tail_fill,
            reserves=self.reserves,
            weights=self.weights,
        )


@dataclass(frozen=True)
class AutomationResult:
    status: RunStatus
    planned: tuple[PlanItem, ...] = ()
    started: tuple[Candidate, ...] = ()
    stop_reason: str | None = None


class FlowerbedBackend(Protocol):
    def scan(self) -> ScanSnapshot:
        ...

    def verify(self, proposed: Candidate) -> Candidate | None:
        ...

    def start(self, proposed: Candidate) -> StartOutcome:
        ...


def _integer(value, name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be an integer") from exc


def _non_negative_float(value, name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{name} must be a number") from exc
    if parsed < 0:
        raise ValueError(f"{name} must not be negative")
    return parsed


def _boolean(value, name: str) -> bool:
    if type(value) is bool:
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "1"}:
            return True
        if normalized in {"false", "no", "0"}:
            return False
    raise TypeError(f"{name} must be a boolean")


def parse_action_config(values: Mapping) -> AutomationConfig:
    mode = ExecutionMode(values.get("execution_mode", ExecutionMode.PLAN_ONLY.value))
    deadline_hours = _integer(values.get("deadline_hours", 24), "deadline_hours")
    max_starts = _integer(values.get("max_starts", 6), "max_starts")
    if deadline_hours < 0:
        raise ValueError("deadline_hours must not be negative")
    if not 1 <= max_starts <= 6:
        raise ValueError("max_starts must be between one and six")
    reserve_keys = (
        "kagayaki_reserve",
        "chosen_reserve",
        "kyoryoku_reserve",
        "nazo_reserve",
    )
    reserve_values = [
        _integer(values.get(key, 0), key)
        for key in reserve_keys
    ]
    if any(value < 0 for value in reserve_values):
        raise ValueError("flower reserves must not be negative")
    return AutomationConfig(
        execution_mode=mode,
        deadline_seconds=deadline_hours * 3600,
        max_starts=max_starts,
        allow_tail_fill=_boolean(
            values.get("allow_tail_fill", False),
            "allow_tail_fill",
        ),
        reserves=dict(zip(FLOWER_ORDER[1:], reserve_values)),
        weights=RatingWeights(
            work_speed=_non_negative_float(
                values.get("work_speed_weight", 0.1),
                "work_speed_weight",
            ),
            stamina=_non_negative_float(
                values.get("stamina_weight", 0.01),
                "stamina_weight",
            ),
        ),
    )


def run_automation(
    config: AutomationConfig,
    backend: FlowerbedBackend,
) -> AutomationResult:
    try:
        snapshot = backend.scan()
    except Exception:
        return AutomationResult(
            status=RunStatus.STOPPED,
            stop_reason="scan_failed",
        )

    initial_plan = tuple(
        select_candidates(
            snapshot.candidates,
            snapshot.active_count,
            config.schedule_config(),
        )
    )
    if config.execution_mode is ExecutionMode.PLAN_ONLY:
        return AutomationResult(
            status=RunStatus.PLANNED,
            planned=initial_plan,
        )

    started: list[Candidate] = []
    excluded_keys = set()
    current_snapshot = snapshot
    while len(started) < config.max_starts:
        remaining = config.max_starts - len(started)
        plan = select_candidates(
            current_snapshot.candidates,
            current_snapshot.active_count,
            config.schedule_config(max_starts=remaining),
            excluded_keys=excluded_keys,
        )
        if not plan:
            return AutomationResult(
                status=RunStatus.COMPLETED,
                planned=initial_plan,
                started=tuple(started),
            )

        proposed = plan[0].candidate
        try:
            verified = backend.verify(proposed)
        except Exception:
            verified = None
        if verified != proposed:
            return AutomationResult(
                status=RunStatus.STOPPED,
                planned=initial_plan,
                started=tuple(started),
                stop_reason="candidate_changed_before_start",
            )

        try:
            outcome = backend.start(proposed)
        except Exception:
            outcome = StartOutcome.UNKNOWN
        if outcome is not StartOutcome.CONFIRMED:
            reason = (
                "start_failed"
                if outcome is StartOutcome.FAILED
                else "start_result_unknown"
            )
            return AutomationResult(
                status=RunStatus.STOPPED,
                planned=initial_plan,
                started=tuple(started),
                stop_reason=reason,
            )

        started.append(proposed)
        if proposed.idempotency_key is not None:
            excluded_keys.add(proposed.idempotency_key)
        if len(started) >= config.max_starts:
            break
        try:
            current_snapshot = backend.scan()
        except Exception:
            return AutomationResult(
                status=RunStatus.STOPPED,
                planned=initial_plan,
                started=tuple(started),
                stop_reason="scan_failed_after_start",
            )

    return AutomationResult(
        status=RunStatus.COMPLETED,
        planned=initial_plan,
        started=tuple(started),
    )
