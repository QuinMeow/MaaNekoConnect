import pytest

from agent.flowerbed.models import Candidate
from agent.flowerbed.parsing import (
    candidate_from_ocr,
    parse_bonus_change,
    parse_duration_seconds,
    parse_integer,
    parse_level_change,
    parse_resource_change,
)


def test_parse_integer_accepts_commas():
    assert parse_integer("219,850") == 219850


def test_parse_bonus_change_uses_popup_values():
    assert parse_bonus_change("+19.0 ▶ +19.5") == (19.0, 19.5)


def test_parse_level_change_reads_current_and_next():
    assert parse_level_change("Lv 38 ▶ 39") == (38, 39)


def test_parse_resource_change_derives_cost_from_actual_balances():
    assert parse_resource_change("219,850 ▶ 209,850") == (219850, 10000)


def test_parse_duration_allows_unbounded_hours():
    assert parse_duration_seconds("強化時間：123:45:06") == 445506


@pytest.mark.parametrize("value", ["99:60:00", "99:00:60", "not a time"])
def test_parse_duration_rejects_invalid_values(value):
    with pytest.raises(ValueError):
        parse_duration_seconds(value)


def test_candidate_idempotency_key_uses_flower_attribute_and_levels():
    candidate = Candidate(
        flower="始まりの花",
        attribute="Food",
        current_level=38,
        next_level=39,
        current_bonus=19.0,
        next_bonus=19.5,
        cost=10000,
        duration_seconds=30300,
        resource_balance=219850,
        active=False,
        button_enabled=True,
        capped=False,
        confidence=0.99,
    )

    assert candidate.idempotency_key == ("始まりの花", "Food", 38, 39)
    assert candidate.bonus_delta == 0.5


def test_candidate_is_built_from_actual_popup_ocr_fields():
    candidate = candidate_from_ocr(
        flower="始まりの花",
        expected_attribute="Food",
        fields={
            "title": "フード強化",
            "levels": "Lv 38 ▶ 39",
            "bonuses": "フード +19.0 ▶ +19.5",
            "resources": "219,850 ▶ 209,850",
            "duration": "強化時間：108:25:00",
            "button_enabled": True,
            "active": False,
            "capped": False,
            "confidence": 0.97,
        },
    )

    assert candidate.current_level == 38
    assert candidate.next_level == 39
    assert candidate.bonus_delta == 0.5
    assert candidate.cost == 10000
    assert candidate.duration_seconds == 390300
    assert candidate.resource_balance == 219850


def test_candidate_rejects_popup_for_a_different_attribute():
    with pytest.raises(ValueError, match="attribute"):
        candidate_from_ocr(
            flower="始まりの花",
            expected_attribute="Food",
            fields={
                "title": "スイーツ強化",
                "levels": "Lv 38 ▶ 39",
                "bonuses": "+19.0 ▶ +19.5",
                "resources": "219,850 ▶ 209,850",
                "duration": "08:25:00",
                "button_enabled": True,
                "active": False,
                "capped": False,
                "confidence": 0.97,
            },
        )
