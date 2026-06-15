import re

from .models import Candidate


_INTEGER_RE = re.compile(r"(?<![\d,])\d[\d,]*(?![\d,])")
_SIGNED_INTEGER_RE = re.compile(r"(?<![\d,])[+-]?\d[\d,]*(?![\d,])")
_NUMBER_RE = re.compile(r"(?<![\d.,])[+-]?\d+(?:[.,]\d+)?(?![\d.,])")
_DURATION_RE = re.compile(r"(?<!\d)(\d+):([0-5]\d):([0-5]\d)(?!\d)")


def parse_integer(text: str) -> int:
    match = _INTEGER_RE.search(text)
    if match is None:
        raise ValueError(f"integer not found: {text!r}")
    return int(match.group().replace(",", ""))


def parse_level_change(text: str) -> tuple[int, int]:
    values = [int(value.replace(",", "")) for value in _INTEGER_RE.findall(text)]
    if len(values) == 1:
        fused = str(values[0])
        consecutive = [
            (int(fused[:index]), int(fused[index:]))
            for index in range(1, len(fused))
            if int(fused[index:]) == int(fused[:index]) + 1
        ]
        if len(consecutive) == 1:
            return consecutive[0]
    if len(values) != 2:
        raise ValueError(f"level change requires two values: {text!r}")
    return values[0], values[1]


def parse_bonus_change(text: str) -> tuple[float, float]:
    values = [
        float(value.replace(",", "."))
        for value in _NUMBER_RE.findall(text)
    ]
    if len(values) != 2:
        raise ValueError(f"bonus change requires two values: {text!r}")
    return values[0], values[1]


def parse_resource_change(text: str) -> tuple[int, int]:
    values = [
        int(value.replace(",", ""))
        for value in _SIGNED_INTEGER_RE.findall(text)
    ]
    if len(values) != 2:
        raise ValueError(f"resource change requires two values: {text!r}")
    before, after = values
    cost = before - after
    if cost <= 0:
        raise ValueError(f"resource balance did not decrease: {text!r}")
    return before, cost


def parse_duration_seconds(text: str) -> int:
    match = _DURATION_RE.search(text)
    if match is None:
        raise ValueError(f"duration not found: {text!r}")
    hours, minutes, seconds = (int(value) for value in match.groups())
    return hours * 3600 + minutes * 60 + seconds


_ATTRIBUTE_LABELS = {
    "Food": ("Food", "フード"),
    "Sweets": ("Sweets", "スイーツ"),
    "Drink": ("Drink", "ドリンク"),
    "Customer Service": ("Customer Service", "接客力"),
    "Work Speed": ("Work Speed", "作業速度"),
    "Stamina": ("Stamina", "スタミナ"),
}


def _attribute_from_title(text: str) -> str:
    for attribute, labels in _ATTRIBUTE_LABELS.items():
        if any(label.lower() in text.lower() for label in labels):
            return attribute
    raise ValueError(f"attribute not found in popup title: {text!r}")


def candidate_from_ocr(
    *,
    flower: str,
    expected_attribute: str,
    fields: dict,
) -> Candidate:
    actual_attribute = _attribute_from_title(str(fields["title"]))
    if actual_attribute != expected_attribute:
        raise ValueError(
            f"popup attribute {actual_attribute!r} did not match "
            f"{expected_attribute!r}"
        )
    current_level, next_level = parse_level_change(str(fields["levels"]))
    current_bonus, next_bonus = parse_bonus_change(str(fields["bonuses"]))
    resource_balance, cost = parse_resource_change(str(fields["resources"]))
    duration_seconds = parse_duration_seconds(str(fields["duration"]))
    for name in ("button_enabled", "active", "capped"):
        if type(fields.get(name)) is not bool:
            raise ValueError(f"{name} must be confirmed as a boolean")
    confidence = float(fields["confidence"])
    if not 0 <= confidence <= 1:
        raise ValueError("confidence must be between zero and one")
    return Candidate(
        flower=flower,
        attribute=expected_attribute,
        current_level=current_level,
        next_level=next_level,
        current_bonus=current_bonus,
        next_bonus=next_bonus,
        cost=cost,
        duration_seconds=duration_seconds,
        resource_balance=resource_balance,
        active=fields["active"],
        button_enabled=fields["button_enabled"],
        capped=fields["capped"],
        confidence=confidence,
    )
