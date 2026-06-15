import json
from pathlib import Path

import pytest

from agent.flowerbed.action import ExecutionMode, parse_action_config
from agent.flowerbed.priority import FLOWER_ORDER


ROOT = Path(__file__).resolve().parents[1]


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def apply_input_override(option, values):
    input_types = {
        item["name"]: item.get("pipeline_type", "string")
        for item in option["inputs"]
    }

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, str) and value.startswith("{") and value.endswith("}"):
            name = value[1:-1]
            raw = values[name]
            if input_types[name] == "int":
                return int(raw)
            if input_types[name] == "bool":
                return str(raw).lower() == "true"
            return str(raw)
        return value

    return replace(option["pipeline_override"])


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

    assert task["option"] == ["FlowerbedSettings"]
    assert list(interface["option"]) == ["FlowerbedSettings"]
    settings = interface["option"]["FlowerbedSettings"]
    assert settings["type"] == "input"
    assert [(item["name"], item["default"]) for item in settings["inputs"]] == [
        ("DeadlineHours", "24"),
        ("MaxStarts", "6"),
        ("AllowTailFill", "false"),
        ("KagayakiReserve", "0"),
        ("ChosenReserve", "0"),
        ("KyoryokuReserve", "0"),
        ("NazoReserve", "0"),
        ("WorkSpeedWeight", "0.1"),
        ("StaminaWeight", "0.01"),
    ]
    assert settings["inputs"][2]["verify"] == "^(?:true|false)$"


def test_settings_override_preserves_all_fields_with_official_placeholders():
    interface = load_json(ROOT / "assets" / "interface.json")
    settings = interface["option"]["FlowerbedSettings"]
    values = {
        "DeadlineHours": "120",
        "MaxStarts": "3",
        "AllowTailFill": "true",
        "KagayakiReserve": "10",
        "ChosenReserve": "20",
        "KyoryokuReserve": "30",
        "NazoReserve": "40",
        "WorkSpeedWeight": "0.2",
        "StaminaWeight": "0.03",
    }

    override = apply_input_override(settings, values)
    params = override["SoleilFlowerbedPlanAndExecute"]["custom_action_param"]

    assert params == {
        "execution_mode": "PlanOnly",
        "deadline_hours": 120,
        "max_starts": 3,
        "allow_tail_fill": "true",
        "kagayaki_reserve": 10,
        "chosen_reserve": 20,
        "kyoryoku_reserve": 30,
        "nazo_reserve": 40,
        "work_speed_weight": "0.2",
        "stamina_weight": "0.03",
    }
    config = parse_action_config(params)
    assert config.execution_mode is ExecutionMode.PLAN_ONLY
    assert config.allow_tail_fill is True
    assert "「" not in json.dumps(interface, ensure_ascii=False)


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


def test_flowerbed_pipeline_uses_bundled_japanese_ocr_model():
    pipeline = load_json(
        ROOT / "assets" / "resource" / "pipeline" / "soleil_flowerbed.json"
    )
    ocr_nodes = [
        node
        for node in pipeline.values()
        if node.get("recognition") == "OCR"
    ]

    assert ocr_nodes
    assert all(node.get("model") == "ja_jp" for node in ocr_nodes)

    model_dir = ROOT / "assets" / "resource" / "model" / "ocr" / "ja_jp"
    source_dir = ROOT / "assets" / "MaaCommonAssets" / "OCR"
    sources = {
        "det.onnx": source_dir / "ppocr_v4" / "zh_cn" / "det.onnx",
        "rec.onnx": source_dir / "ppocr_v3" / "ja_jp" / "rec.onnx",
        "keys.txt": source_dir / "ppocr_v3" / "ja_jp" / "keys.txt",
    }
    for filename, source in sources.items():
        bundled = model_dir / filename
        assert bundled.is_file()
        assert bundled.stat().st_size > 0
        assert bundled.read_bytes() == source.read_bytes()
