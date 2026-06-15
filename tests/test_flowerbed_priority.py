from dataclasses import replace

import pytest

from agent.flowerbed.models import Candidate
from agent.flowerbed.priority import (
    ATTRIBUTE_ORDER,
    FLOWER_ORDER,
    RatingWeights,
    ScheduleConfig,
    rating_delta,
    select_candidates,
)


def candidate(
    *,
    flower="始まりの花",
    attribute="Food",
    current_level=1,
    next_level=2,
    current_bonus=0.0,
    next_bonus=1.0,
    cost=1,
    duration_seconds=3600,
    resource_balance=10000,
    active=False,
    button_enabled=True,
    capped=False,
    confidence=0.99,
):
    return Candidate(
        flower=flower,
        attribute=attribute,
        current_level=current_level,
        next_level=next_level,
        current_bonus=current_bonus,
        next_bonus=next_bonus,
        cost=cost,
        duration_seconds=duration_seconds,
        resource_balance=resource_balance,
        active=active,
        button_enabled=button_enabled,
        capped=capped,
        confidence=confidence,
    )


def config(**changes):
    values = {
        "deadline_seconds": 24 * 3600,
        "max_starts": 6,
        "allow_tail_fill": False,
        "reserves": {},
        "weights": RatingWeights(),
    }
    values.update(changes)
    return ScheduleConfig(**values)


@pytest.mark.parametrize("attribute", ["Food", "Sweets", "Drink"])
def test_food_sweets_and_drink_use_community_rating_weight(attribute):
    assert rating_delta(candidate(attribute=attribute)) == pytest.approx(0.1)


def test_customer_service_is_one_hundred_times_food():
    customer = rating_delta(candidate(attribute="Customer Service"))
    food = rating_delta(candidate(attribute="Food"))

    assert customer == pytest.approx(food * 100)


def test_work_speed_and_stamina_use_configurable_fallbacks():
    weights = RatingWeights(work_speed=0.2, stamina=0.03)

    assert rating_delta(candidate(attribute="Work Speed"), weights) == pytest.approx(
        0.2
    )
    assert rating_delta(candidate(attribute="Stamina"), weights) == pytest.approx(
        0.03
    )


def test_cost_boundary_includes_10000_and_excludes_10001():
    allowed = candidate(attribute="Food", cost=10000, resource_balance=10000)
    denied = candidate(attribute="Drink", cost=10001, resource_balance=20000)

    selected = select_candidates([allowed, denied], 0, config())

    assert [item.candidate for item in selected] == [allowed]


def test_global_six_slots_account_for_existing_active_items():
    candidates = [
        candidate(attribute=attribute, current_level=index, next_level=index + 1)
        for index, attribute in enumerate(ATTRIBUTE_ORDER, start=1)
    ]

    selected = select_candidates(candidates, 2, config())

    assert len(selected) == 4


def test_same_flower_can_start_multiple_attributes():
    candidates = [
        candidate(attribute="Food", cost=3, resource_balance=10),
        candidate(attribute="Sweets", cost=3, resource_balance=10),
    ]

    selected = select_candidates(candidates, 0, config())

    assert {item.candidate.attribute for item in selected} == {"Food", "Sweets"}


def test_resource_cost_is_accumulated_per_flower():
    candidates = [
        candidate(attribute="Food", cost=6, resource_balance=10),
        candidate(attribute="Sweets", cost=6, resource_balance=10),
    ]

    selected = select_candidates(candidates, 0, config())

    assert len(selected) == 1


def test_scarce_flower_reserve_is_preserved():
    scarce = FLOWER_ORDER[1]
    upgrade = candidate(flower=scarce, cost=6, resource_balance=10)

    selected = select_candidates(
        [upgrade],
        0,
        config(reserves={scarce: 5}),
    )

    assert selected == []


def test_customer_service_ui_cap_is_excluded():
    capped = candidate(attribute="Customer Service", capped=True)

    assert select_candidates([capped], 0, config()) == []


def test_higher_deadline_rating_wins_before_rating_per_second():
    larger = candidate(
        attribute="Food",
        next_bonus=2.0,
        duration_seconds=8 * 3600,
    )
    faster = candidate(
        attribute="Sweets",
        next_bonus=1.0,
        duration_seconds=60,
    )

    selected = select_candidates(
        [faster, larger],
        0,
        config(max_starts=1),
    )

    assert selected[0].candidate is larger


def test_scarce_consumption_wins_before_rating_per_second():
    slow = candidate(
        flower=FLOWER_ORDER[1],
        attribute="Food",
        duration_seconds=3600,
        cost=10000,
    )
    fast = candidate(
        flower=FLOWER_ORDER[0],
        attribute="Sweets",
        duration_seconds=60,
    )

    selected = select_candidates(
        [slow, fast],
        0,
        config(max_starts=1),
    )

    assert selected[0].candidate is slow


def test_rating_per_second_breaks_equal_rating_and_scarce_cost_tie():
    slow = candidate(
        flower=FLOWER_ORDER[1],
        attribute="Food",
        duration_seconds=3600,
    )
    fast = candidate(
        flower=FLOWER_ORDER[2],
        attribute="Sweets",
        duration_seconds=60,
    )

    selected = select_candidates([slow, fast], 0, config(max_starts=1))

    assert selected[0].candidate is fast


def test_deadline_excludes_long_task_without_tail_fill():
    long_task = candidate(duration_seconds=25 * 3600)

    assert select_candidates([long_task], 0, config()) == []


def test_tail_fill_uses_only_scarce_flowers_and_scores_zero_deadline_rating():
    abundant = candidate(flower=FLOWER_ORDER[0], duration_seconds=25 * 3600)
    scarce = candidate(flower=FLOWER_ORDER[1], duration_seconds=25 * 3600)

    selected = select_candidates(
        [abundant, scarce],
        0,
        config(allow_tail_fill=True),
    )

    assert [item.candidate for item in selected] == [scarce]
    assert selected[0].deadline_rating == 0


def test_tail_fill_can_use_remaining_slot_after_deadline_work_is_selected():
    deadline_task = candidate(
        flower=FLOWER_ORDER[0],
        attribute="Food",
        duration_seconds=60,
    )
    tail_task = candidate(
        flower=FLOWER_ORDER[1],
        attribute="Sweets",
        duration_seconds=25 * 3600,
    )

    selected = select_candidates(
        [tail_task, deadline_task],
        0,
        config(max_starts=2, allow_tail_fill=True),
    )

    assert [item.candidate for item in selected] == [deadline_task, tail_task]


def test_scarce_consumption_breaks_equal_rating_and_rate_tie():
    abundant = candidate(flower=FLOWER_ORDER[0], attribute="Food", cost=5)
    scarce = replace(abundant, flower=FLOWER_ORDER[1])

    selected = select_candidates(
        [abundant, scarce],
        0,
        config(max_starts=1),
    )

    assert selected[0].candidate is scarce


def test_final_tie_break_is_stable_flower_then_attribute_order():
    later = candidate(flower=FLOWER_ORDER[2], attribute=ATTRIBUTE_ORDER[2])
    earlier = candidate(flower=FLOWER_ORDER[1], attribute=ATTRIBUTE_ORDER[1])

    selected = select_candidates(
        [later, earlier],
        0,
        config(max_starts=1),
    )

    assert selected[0].candidate is earlier


@pytest.mark.parametrize(
    "changes",
    [
        {"active": True},
        {"button_enabled": False},
        {"confidence": 0.79},
        {"cost": 0},
        {"duration_seconds": None},
        {"next_bonus": None},
        {"resource_balance": None},
    ],
)
def test_uncertain_or_invalid_candidates_fail_closed(changes):
    assert select_candidates([candidate(**changes)], 0, config()) == []


def test_invalid_active_count_fails_closed():
    assert select_candidates([candidate()], None, config()) == []
    assert select_candidates([candidate()], 7, config()) == []


def test_duplicate_idempotency_keys_are_considered_once():
    original = candidate()
    duplicate = replace(original)

    selected = select_candidates([original, duplicate], 0, config())

    assert len(selected) == 1
