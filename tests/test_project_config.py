import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_resources_have_unique_nodes_and_resolvable_references(pipelines):
    def visit(value):
        if isinstance(value, dict):
            yield value
            for child in value.values():
                yield from visit(child)
        elif isinstance(value, list):
            for child in value:
                yield from visit(child)

    for name, node in pipelines.items():
        for item in visit(node):
            for field in ("next", "on_error", "all_of", "any_of"):
                for target in item.get(field, []):
                    if isinstance(target, str):
                        assert target.startswith("[Anchor]") or target in pipelines, (name, target)
            for target in item.get("anchor", {}).values():
                assert target in pipelines, (name, target)
            templates = item.get("template", [])
            for template in [templates] if isinstance(templates, str) else templates:
                assert (ROOT / "assets/resource/image" / template).is_file(), (name, template)
    interface = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))
    assert all(task["entry"] in pipelines for task in interface["task"])


def test_tests_stay_within_the_physical_line_budget():
    for path in (ROOT / "tests").rglob("*.py"):
        assert len(path.read_text("utf-8").splitlines()) <= 200, path.name


def test_public_tasks_use_operation_names_without_framework_diagnostics(pipelines):
    tasks = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))["task"]
    assert "TestLaunchAndCapture" not in pipelines and "TestCaptureScreen" not in pipelines
    assert all(not task["entry"].startswith("Test") for task in tasks)
    names = {task["entry"]: task.get("label", task["name"]) for task in tasks}
    assert names["DailyExchange_Start"] == "交换所兑换"
    assert names["DailyVR_Start"] == "VR猫爬塔"
    for task in tasks:
        for name in (task["name"], names[task["entry"]]):
            assert not any(word in name for word in ("日常：", "一次", "一件", "用尽"))
            assert not any(char.isdigit() for char in name)
        assert pipelines[task["entry"]]["doc"] == names[task["entry"]]
