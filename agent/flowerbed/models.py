from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


IdempotencyKey = tuple[str, str, int, int]


@dataclass(frozen=True)
class Candidate:
    flower: str
    attribute: str
    current_level: Optional[int]
    next_level: Optional[int]
    current_bonus: Optional[float]
    next_bonus: Optional[float]
    cost: Optional[int]
    duration_seconds: Optional[int]
    resource_balance: Optional[int]
    active: Optional[bool]
    button_enabled: Optional[bool]
    capped: Optional[bool]
    confidence: float

    @property
    def idempotency_key(self) -> Optional[IdempotencyKey]:
        if self.current_level is None or self.next_level is None:
            return None
        return (
            self.flower,
            self.attribute,
            self.current_level,
            self.next_level,
        )

    @property
    def bonus_delta(self) -> Optional[float]:
        if self.current_bonus is None or self.next_bonus is None:
            return None
        return self.next_bonus - self.current_bonus

    @property
    def complete(self) -> bool:
        return all(
            value is not None
            for value in (
                self.current_level,
                self.next_level,
                self.current_bonus,
                self.next_bonus,
                self.cost,
                self.duration_seconds,
                self.resource_balance,
                self.active,
                self.button_enabled,
                self.capped,
            )
        )


@dataclass(frozen=True)
class ScanSnapshot:
    active_count: Optional[int]
    candidates: tuple[Candidate, ...]
