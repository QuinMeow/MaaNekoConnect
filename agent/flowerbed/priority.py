from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations
from typing import Collection, Mapping, Sequence

from .models import Candidate, IdempotencyKey


FLOWER_ORDER = (
    "始まりの花",
    "輝きの花",
    "挑戦の花",
    "協力の花",
    "謎めきの花",
)
ATTRIBUTE_ORDER = (
    "Food",
    "Sweets",
    "Drink",
    "Customer Service",
    "Work Speed",
    "Stamina",
)
SCARCE_FLOWERS = frozenset(FLOWER_ORDER[1:])
MIN_CONFIDENCE = 0.8


@dataclass(frozen=True)
class RatingWeights:
    food: float = 0.1
    sweets: float = 0.1
    drink: float = 0.1
    customer_service: float = 10.0
    work_speed: float = 0.1
    stamina: float = 0.01

    def for_attribute(self, attribute: str) -> float:
        weights = {
            "Food": self.food,
            "Sweets": self.sweets,
            "Drink": self.drink,
            "Customer Service": self.customer_service,
            "Work Speed": self.work_speed,
            "Stamina": self.stamina,
        }
        try:
            return weights[attribute]
        except KeyError as exc:
            raise ValueError(f"unknown flowerbed attribute: {attribute!r}") from exc


@dataclass(frozen=True)
class ScheduleConfig:
    deadline_seconds: int
    max_starts: int = 6
    allow_tail_fill: bool = False
    reserves: Mapping[str, int] = field(default_factory=dict)
    weights: RatingWeights = field(default_factory=RatingWeights)


@dataclass(frozen=True)
class PlanItem:
    candidate: Candidate
    deadline_rating: float


def rating_delta(
    candidate: Candidate,
    weights: RatingWeights | None = None,
) -> float:
    delta = candidate.bonus_delta
    if delta is None:
        raise ValueError("candidate bonus delta is incomplete")
    return delta * (weights or RatingWeights()).for_attribute(candidate.attribute)


def _stable_key(candidate: Candidate) -> tuple[int, int, int, int]:
    flower_index = (
        FLOWER_ORDER.index(candidate.flower)
        if candidate.flower in FLOWER_ORDER
        else len(FLOWER_ORDER)
    )
    attribute_index = (
        ATTRIBUTE_ORDER.index(candidate.attribute)
        if candidate.attribute in ATTRIBUTE_ORDER
        else len(ATTRIBUTE_ORDER)
    )
    return (
        flower_index,
        attribute_index,
        candidate.current_level or -1,
        candidate.next_level or -1,
    )


def _eligible(candidate: Candidate, config: ScheduleConfig) -> bool:
    if not candidate.complete or candidate.confidence < MIN_CONFIDENCE:
        return False
    if candidate.flower not in FLOWER_ORDER or candidate.attribute not in ATTRIBUTE_ORDER:
        return False
    if candidate.active is not False:
        return False
    if candidate.button_enabled is not True or candidate.capped is not False:
        return False
    if candidate.cost is None or not 1 <= candidate.cost <= 10000:
        return False
    if candidate.duration_seconds is None or candidate.duration_seconds <= 0:
        return False
    if candidate.resource_balance is None or candidate.resource_balance < candidate.cost:
        return False
    if (
        candidate.current_level is None
        or candidate.next_level is None
        or candidate.next_level <= candidate.current_level
    ):
        return False
    delta = candidate.bonus_delta
    if delta is None or delta <= 0:
        return False
    reserve = config.reserves.get(candidate.flower, 0)
    return reserve >= 0 and candidate.resource_balance - reserve >= candidate.cost


def _deduplicate(candidates: Sequence[Candidate]) -> list[Candidate]:
    by_key: dict[IdempotencyKey, Candidate] = {}
    conflicts: set[IdempotencyKey] = set()
    for candidate in candidates:
        key = candidate.idempotency_key
        if key is None:
            continue
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = candidate
        elif existing != candidate:
            conflicts.add(key)
    return [
        candidate
        for key, candidate in by_key.items()
        if key not in conflicts
    ]


def _resources_fit(
    chosen: Sequence[Candidate],
    config: ScheduleConfig,
    initial_costs: Mapping[str, int],
) -> bool:
    costs = dict(initial_costs)
    balances: dict[str, int] = {}
    for candidate in chosen:
        costs[candidate.flower] = costs.get(candidate.flower, 0) + int(candidate.cost)
        balance = int(candidate.resource_balance)
        existing = balances.get(candidate.flower)
        if existing is not None and existing != balance:
            return False
        balances[candidate.flower] = balance
    for flower, cost in costs.items():
        if flower not in balances:
            continue
        if cost > balances[flower] - config.reserves.get(flower, 0):
            return False
    return True


def _subset_score(
    chosen: Sequence[Candidate],
    config: ScheduleConfig,
    deadline_rating: bool,
) -> tuple[float, float, int, int]:
    ratings = [rating_delta(candidate, config.weights) for candidate in chosen]
    return (
        sum(ratings) if deadline_rating else 0.0,
        sum(
            int(candidate.cost)
            for candidate in chosen
            if candidate.flower in SCARCE_FLOWERS
        ),
        sum(
            rating / int(candidate.duration_seconds)
            for candidate, rating in zip(chosen, ratings)
        ),
        -sum(int(candidate.duration_seconds) for candidate in chosen),
    )


def _best_subset(
    candidates: Sequence[Candidate],
    slots: int,
    config: ScheduleConfig,
    *,
    deadline_rating: bool,
    initial_costs: Mapping[str, int] | None = None,
) -> tuple[Candidate, ...]:
    initial_costs = initial_costs or {}
    best: tuple[Candidate, ...] = ()
    best_score = _subset_score(best, config, deadline_rating)
    best_stable: tuple[tuple[int, int, int, int], ...] = ()
    for size in range(1, min(slots, len(candidates)) + 1):
        for chosen in combinations(candidates, size):
            if not _resources_fit(chosen, config, initial_costs):
                continue
            score = _subset_score(chosen, config, deadline_rating)
            stable = tuple(sorted(_stable_key(candidate) for candidate in chosen))
            if score > best_score or (score == best_score and stable < best_stable):
                best = chosen
                best_score = score
                best_stable = stable
    return best


def _item_order(item: PlanItem, config: ScheduleConfig) -> tuple:
    candidate = item.candidate
    rating = rating_delta(candidate, config.weights)
    return (
        item.deadline_rating == 0,
        -item.deadline_rating,
        -(
            int(candidate.cost)
            if candidate.flower in SCARCE_FLOWERS
            else 0
        ),
        -(rating / int(candidate.duration_seconds)),
        int(candidate.duration_seconds),
        _stable_key(candidate),
    )


def select_candidates(
    candidates: Sequence[Candidate],
    active_count: int | None,
    config: ScheduleConfig,
    excluded_keys: Collection[IdempotencyKey] = (),
) -> list[PlanItem]:
    if active_count is None or not 0 <= active_count <= 6:
        return []
    if not 1 <= config.max_starts <= 6 or config.deadline_seconds < 0:
        return []
    slots = min(6 - active_count, config.max_starts)
    if slots <= 0:
        return []

    excluded = set(excluded_keys)
    eligible = [
        candidate
        for candidate in _deduplicate(candidates)
        if candidate.idempotency_key not in excluded and _eligible(candidate, config)
    ]
    deadline_candidates = [
        candidate
        for candidate in eligible
        if int(candidate.duration_seconds) <= config.deadline_seconds
    ]
    selected = list(
        _best_subset(
            deadline_candidates,
            slots,
            config,
            deadline_rating=True,
        )
    )

    items = [
        PlanItem(
            candidate=candidate,
            deadline_rating=rating_delta(candidate, config.weights),
        )
        for candidate in selected
    ]
    remaining_slots = slots - len(selected)
    if config.allow_tail_fill and remaining_slots > 0:
        selected_keys = {candidate.idempotency_key for candidate in selected}
        tail_candidates = [
            candidate
            for candidate in eligible
            if candidate.idempotency_key not in selected_keys
            and candidate.flower in SCARCE_FLOWERS
            and int(candidate.duration_seconds) > config.deadline_seconds
        ]
        initial_costs: dict[str, int] = {}
        for candidate in selected:
            initial_costs[candidate.flower] = (
                initial_costs.get(candidate.flower, 0) + int(candidate.cost)
            )
        tail = _best_subset(
            tail_candidates,
            remaining_slots,
            config,
            deadline_rating=False,
            initial_costs=initial_costs,
        )
        items.extend(PlanItem(candidate=candidate, deadline_rating=0.0) for candidate in tail)

    return sorted(items, key=lambda item: _item_order(item, config))
