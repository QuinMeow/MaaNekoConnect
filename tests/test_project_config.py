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


def test_launch_pipeline_starts_only_the_target_game_and_captures_png(pipelines):
    start = pipelines["TestLaunchAndCapture"]
    assert start["action"] == "StartApp"
    assert start["package"] == "jp.goodsmile.nekoconne"
    assert start["post_delay"] >= 20000
    capture = pipelines[start["next"][0]]
    assert capture["action"] == "Screencap" and capture["format"] == "png"
