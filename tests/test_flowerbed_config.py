import json
from pathlib import Path

import pytest

from agent.flowerbed.action import ExecutionMode, parse_action_config
from agent.flowerbed.priority import FLOWER_ORDER


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_action_config_defaults_are_safe():
    config = parse_action_config({})

    assert config.execution_mode is ExecutionMode.PLAN_ONLY
    assert config.deadline_seconds == 24 * 3600
    assert config.max_starts == 6
    assert config.allow_tail_fill is False
    assert config.reserves == {flower: 0 for flower in FLOWER_ORDER[1:]}
    assert config.weights.work_speed == pytest.approx(0.1)
    assert config.weights.stamina == pytest.approx(0.01)


def test_action_config_parses_interface_values():
    config = parse_action_config(
        {
            "execution_mode": "Execute",
            "deadline_hours": 120,
            "max_starts": 3,
            "allow_tail_fill": True,
            "kagayaki_reserve": 10,
            "chosen_reserve": 20,
            "kyoryoku_reserve": 30,
            "nazo_reserve": 40,
            "work_speed_weight": "0.2",
            "stamina_weight": "0.03",
        }
    )

    assert config.execution_mode is ExecutionMode.EXECUTE
    assert config.deadline_seconds == 120 * 3600
    assert config.max_starts == 3
    assert config.allow_tail_fill is True
    assert config.reserves == dict(zip(FLOWER_ORDER[1:], [10, 20, 30, 40]))
    assert config.weights.work_speed == pytest.approx(0.2)
    assert config.weights.stamina == pytest.approx(0.03)


@pytest.mark.parametrize(
    "values",
    [
        {"max_starts": 0},
        {"max_starts": 7},
        {"deadline_hours": -1},
        {"kagayaki_reserve": -1},
        {"work_speed_weight": "-0.1"},
        {"execution_mode": "ClickEverything"},
    ],
)
def test_action_config_rejects_unsafe_values(values):
    with pytest.raises((TypeError, ValueError)):
        parse_action_config(values)


def test_public_task_exposes_supported_options_with_safe_defaults():
    interface = load_json(ROOT / "assets" / "interface.json")
    task = next(
        task
        for task in interface["task"]
        if task["entry"] == "SoleilFlowerbedAutoUpgrade"
    )

    assert task["option"] == [
        "FlowerbedExecutionMode",
        "FlowerbedDeadlineHours",
        "FlowerbedMaxStarts",
        "FlowerbedAllowTailFill",
        "FlowerbedKagayakiReserve",
        "FlowerbedChosenReserve",
        "FlowerbedKyoryokuReserve",
        "FlowerbedNazoReserve",
        "FlowerbedWorkSpeedWeight",
        "FlowerbedStaminaWeight",
    ]
    assert interface["option"]["FlowerbedExecutionMode"]["default_case"] == "PlanOnly"
    assert interface["option"]["FlowerbedDeadlineHours"]["inputs"][0]["default"] == "24"
    assert interface["option"]["FlowerbedMaxStarts"]["inputs"][0]["default"] == "6"
    assert interface["option"]["FlowerbedAllowTailFill"]["default_case"] == "No"
    for name in (
        "FlowerbedKagayakiReserve",
        "FlowerbedChosenReserve",
        "FlowerbedKyoryokuReserve",
        "FlowerbedNazoReserve",
    ):
        assert interface["option"][name]["inputs"][0]["default"] == "0"


def test_pipeline_uses_json_for_navigation_ocr_and_fixed_actions():
    pipeline = load_json(
        ROOT / "assets" / "resource" / "pipeline" / "soleil_flowerbed.json"
    )

    assert pipeline["SoleilFlowerbedAutoUpgrade"]["action"] == "StartApp"
    assert pipeline["SoleilFlowerbedAutoUpgrade"]["package"] == "jp.goodsmile.nekoconne"
    action = pipeline["SoleilFlowerbedPlanAndExecute"]
    assert action["action"] == "Custom"
    assert action["custom_action"] == "SoleilFlowerbedAuto"
    assert action["custom_action_param"]["execution_mode"] == "PlanOnly"
    assert pipeline["SoleilFlowerbedReadLevels"]["recognition"] == "OCR"
    assert pipeline["SoleilFlowerbedReadDuration"]["recognition"] == "OCR"
    assert pipeline["SoleilFlowerbedOpenFood"]["action"] == "Click"
    assert pipeline["SoleilFlowerbedScrollToLastFlower"]["action"] == "Swipe"


def test_pipeline_never_uses_acceleration_items_or_guild_commissions():
    text = (
        ROOT / "assets" / "resource" / "pipeline" / "soleil_flowerbed.json"
    ).read_text(encoding="utf-8")

    assert "加速" not in text
    assert "委托" not in text
    assert "依頼" not in text
