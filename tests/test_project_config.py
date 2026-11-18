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

    interface = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))
    definitions = list(pipelines.items())
    for item in visit(interface):
        for name, override in item.get("pipeline_override", {}).items():
            assert name in pipelines, name
            definitions.append((name, override))
    for name, node in definitions:
        for item in visit(node):
            for field in ("next", "on_error", "all_of", "any_of"):
                for target in item.get(field, []):
                    if isinstance(target, str):
                        assert target.startswith("[Anchor]") or target.removeprefix("[JumpBack]") in pipelines, (name, target)
            for target in item.get("anchor", {}).values():
                assert target in pipelines, (name, target)
            templates = item.get("template", [])
            for template in [templates] if isinstance(templates, str) else templates:
                assert (ROOT / "assets/resource/image" / template).is_file(), (name, template)
    assert all(task["entry"] in pipelines for task in interface["task"])


def test_tests_stay_within_the_physical_line_budget():
    for path in (ROOT / "tests").rglob("*.py"):
        assert len(path.read_text("utf-8").splitlines()) <= 200, path.name


def test_business_tools_do_not_reintroduce_a_cli():
    for name in ("run_daily.py", "run_soleil_upgrade.py", "soleil_options.py"):
        assert not (ROOT / "tools" / name).exists()


def test_public_tasks_exclude_framework_diagnostics(pipelines):
    tasks = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))["task"]
    assert "TestLaunchAndCapture" not in pipelines and "TestCaptureScreen" not in pipelines
    assert all(not task["entry"].startswith("Test") for task in tasks)
