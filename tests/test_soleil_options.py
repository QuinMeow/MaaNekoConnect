import itertools
import json
from pathlib import Path

import pytest
from soleil_options import build_schedule_overrides, build_soleil_overrides


ROOT = Path(__file__).resolve().parents[1]


def interface_overrides(values):
    interface = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))
    overrides = []

    def resolve(name):
        definition = interface["option"][name]
        if definition["type"] == "input":
            text = json.dumps(definition["pipeline_override"])
            for item in definition["inputs"]:
                value = str(values.get(item["name"], item["default"]))
                text = text.replace('"{' + item["name"] + '}"', value)
            overrides.append(json.loads(text))
            return
        selected = values.get(name, definition["default_case"])
        case = next(item for item in definition["cases"] if item["name"] == selected)
        overrides.append(case.get("pipeline_override", {}))
        for child in case.get("option", []):
            resolve(child)

    task = next(task for task in interface["task"] if task["entry"] == "FurnitureSchedule_Start")
    for name in task["option"]:
        resolve(name)
    return overrides


def resolve_interface(values):
    resolved = {}
    for override in interface_overrides(values):
        for name, fields in override.items():
            # MaaFramework replaces node fields, including whole custom parameter objects.
            resolved.setdefault(name, {}).update(fields)
    return resolved


@pytest.mark.parametrize("keep,order,placed,upgradeable,auto_request", list(itertools.product(
    (True, False), ("lv_asc", "lv_desc"), (True, False), (True, False), (True, False),
)))
def test_editor_and_cli_resolve_the_same_active_options(pipelines, keep, order, placed, upgradeable, auto_request):
    values = {"UseExistingSort": "Yes" if keep else "No", "SortOrder": order,
              "OnlyPlaced": "Yes" if placed else "No", "OnlyUpgradeable": "Yes" if upgradeable else "No",
              "AutoRequest": "Yes" if auto_request else "No"}
    expected = build_soleil_overrides(keep, order, placed, upgradeable, auto_request)
    expected.update(build_schedule_overrides())
    resolved = resolve_interface(values)
    for name, fields in expected.items():
        for key, value in fields.items():
            assert resolved.get(name, {}).get(key, pipelines[name].get(key)) == value
    assert resolved.keys() <= expected.keys()


@pytest.mark.parametrize("mode,rounds,seconds", [
    ("single", 1, 60), ("fixed", 3, 90), ("shortest", 1, 10), ("longest", 10000, 86400),
])
def test_editor_schedule_matches_cli(pipelines, mode, rounds, seconds):
    resolved = resolve_interface({"FurnitureSchedule": mode, "Rounds": rounds, "Seconds": seconds})
    expected = build_soleil_overrides()
    expected.update(build_schedule_overrides(rounds, seconds, mode))
    for name, fields in expected.items():
        for key, value in fields.items():
            assert resolved.get(name, {}).get(key, pipelines[name].get(key)) == value
    assert resolved.keys() <= expected.keys()


@pytest.mark.parametrize("mode", ["fixed", "shortest", "longest"])
def test_native_ordered_editor_overrides_preserve_mode_and_interval(native, mode):
    from maa.custom_action import CustomAction
    from agent.furniture_timer import load_state, register_furniture_timer

    states = []

    class Inspect(CustomAction):
        def run(self, context, argv):
            states.append(load_state(context))
            return True

    register_furniture_timer(native.resource)
    assert native.resource.register_custom_action("InspectOptions", Inspect())
    overrides = interface_overrides({"FurnitureSchedule": mode, "Rounds": 3, "Seconds": 90})
    overrides.append({"FurnitureSchedule_Dispatch": {
        "recognition": "DirectHit", "action": "Custom", "custom_action": "InspectOptions",
        "pre_delay": 0, "post_delay": 0, "next": [],
    }})
    native.run("FurnitureSchedule_Start", overrides)
    assert len(states) == 1
    assert states[0]["mode"] == mode and states[0]["seconds"] == 90


def test_partial_custom_params_do_not_inherit_missing_operation(native):
    from agent.furniture_timer import register_furniture_timer

    register_furniture_timer(native.resource)
    overrides = [
        {"TestReplace": {"recognition": "DirectHit", "action": "Custom", "post_delay": 0,
                         "custom_action": "FurnitureTimerControl",
                         "custom_action_param": {"op": "config", "mode": "shortest", "seconds": 60}}},
        {"TestReplace": {"custom_action_param": {"seconds": 90}}},
    ]
    job = native.tasker.post_task("TestReplace", overrides).wait()
    assert not job.succeeded


def test_defaults_preserve_sort_and_do_not_share_mutable_overrides(pipelines):
    defaults = build_soleil_overrides()
    assert defaults["FurnitureEnhance_Prepare"]["next"] == ["FurnitureEnhance_ScrollTop"]
    assert defaults["FurnitureEnhance_AfterStart"]["anchor"]["FurnitureEnhance_PostRound"] == (
        "FurnitureEnhance_ReturnForRequest"
    )
    for name, fields in defaults.items():
        for key, value in fields.items():
            assert pipelines[name][key] == value
    defaults["FurnitureEnhance_Prepare"]["next"].clear()
    assert build_soleil_overrides()["FurnitureEnhance_Prepare"]["next"]


@pytest.mark.parametrize("name", ["use_existing_sort", "only_placed", "only_upgradeable", "auto_request"])
@pytest.mark.parametrize("value", ["false", 0, None])
def test_switches_require_actual_booleans(name, value):
    with pytest.raises(ValueError, match=name):
        build_soleil_overrides(**{name: value})


@pytest.mark.parametrize("value", ["LV", "", None, True])
def test_unknown_sort_is_rejected_even_when_hidden(value):
    with pytest.raises(ValueError):
        build_soleil_overrides(sort_order=value)


@pytest.mark.parametrize("kwargs", [
    {"rounds": 0}, {"rounds": 10001}, {"rounds": True}, {"rounds": 1.5},
    {"interval": 9}, {"interval": 86401}, {"interval": True}, {"interval": "60"},
    {"wait_mode": "unknown"}, {"wait_mode": "single", "rounds": 2},
])
def test_invalid_schedules_fail_before_execution(kwargs):
    with pytest.raises(ValueError):
        build_schedule_overrides(**kwargs)
