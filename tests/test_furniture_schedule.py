import json
from pathlib import Path

import pytest


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
        selected = values.get(name, ["Furniture"] if definition["type"] == "checkbox" else definition["default_case"])
        for case in definition["cases"]:
            if case["name"] in (selected if isinstance(selected, list) else [selected]):
                overrides.append(case.get("pipeline_override", {}))
                for child in case.get("option", []):
                    resolve(child)

    task = next(task for task in interface["task"] if task["entry"] == "Soleil_DailyStart")
    for name in task["option"]:
        resolve(name)
    return overrides


def test_furniture_resource_is_consolidated(pipelines):
    directory = ROOT / "assets/resource/pipeline"
    assert (directory / "furniture.json").is_file()
    assert not list(directory.glob("furniture_*.json"))
    assert not (directory / "soleil_shop.json").exists()
    assert not (directory / "soleil_upgrade.json").exists()
    assert "FurnitureSchedule_Start" in pipelines
    assert not {"SoleilUpgradeLoop", "FurnitureEnhance_Round", "FurnitureEnhance_Complete"} & pipelines.keys()


@pytest.mark.parametrize("rounds,cap", [(1, 5), (3, 2), (3, 15)])
def test_rounds_wait_between_runs_and_recovery_does_not_refund_budget(native, pipelines, rounds, cap):
    overrides = {
        name: {"pre_delay": 0, "post_delay": 0, "timeout": 1, "rate_limit": 0}
        for name in pipelines
    }
    graph = {
        "FurnitureTimer_Start": ["[Anchor]FurnitureTimer_Return"],
        "FurnitureEnhance_BeginRound": ["FurnitureEnhance_SessionSpendPermit", "FurnitureEnhance_SessionLimit"],
        "FurnitureEnhance_SessionSpendPermit": ["FurnitureEnhance_Start1"],
        "FurnitureEnhance_Start1": ["FurnitureEnhance_Started"],
        "FurnitureEnhance_Started": ["WaitForTransition"],
        "WaitForTransition": ["NeverMatches"],
        "CommonRecoveryEnter": ["CommonRecoveryDispatch"],
        "CommonRecoveryDispatch": ["CommonRecoveryRecovered"],
        "CommonRecoveryRecovered": ["[Anchor]CommonRecoveryResume"],
        "FurnitureEnhance_RoundFinish": ["Soleil_RequestSupport"],
        "Soleil_RequestSupport": ["FurnitureEnhance_RoundComplete"],
        "FurnitureEnhance_SessionLimit": ["FurnitureEnhance_RoundComplete"],
        "FurnitureEnhance_RoundComplete": ["[Anchor]FurnitureEnhance_OnComplete"],
    }
    # Only the scheduler and native hit counters are under test; business actions are simulated.
    overrides.update({name: {"recognition": "DirectHit", "action": "DoNothing", "next": targets,
                             "pre_delay": 0, "post_delay": 0, "timeout": 1, "rate_limit": 0}
                      for name, targets in graph.items()})
    overrides["FurnitureTimer_Config"]["action"] = "DoNothing"
    overrides["FurnitureTimer_IntervalConfig"]["action"] = "DoNothing"
    overrides["FurnitureSchedule_Permit"]["max_hit"] = rounds
    overrides["FurnitureEnhance_SessionSpendPermit"]["max_hit"] = cap
    overrides["FurnitureEnhance_BeginRound"]["anchor"] = {
        "CommonRecoveryResume": "FurnitureEnhance_RoundFinish",
    }
    overrides["WaitForTransition"]["on_error"] = ["CommonRecoveryEnter"]
    overrides["NeverMatches"] = {
        "recognition": "ColorMatch", "method": 4, "roi": [0, 0, 1, 1],
        "lower": [1, 1, 1], "upper": [2, 2, 2], "count": 1,
    }
    detail = native.run("FurnitureSchedule_Start", overrides)
    names = [node.name for node in detail.nodes]
    assert names.count("FurnitureSchedule_Permit") == rounds
    assert names.count("FurnitureSchedule_FirstRound") == 1
    assert names.count("FurnitureTimer_Start") == rounds - 1
    for name in ("FurnitureEnhance_SessionSpendPermit", "Soleil_RequestSupport", "CommonRecoveryEnter"):
        assert names.count(name) == min(rounds, cap)
    assert names[-1] == "FurnitureSchedule_Complete"


@pytest.mark.parametrize("keep_sort,auto_request", [(True, True), (True, False), (False, True), (False, False)])
def test_interface_selects_sort_and_request_without_changing_round_limit(keep_sort, auto_request):
    values = {"UseExistingSort": "Yes" if keep_sort else "No",
              "AutoRequest": "Yes" if auto_request else "No"}
    resolved = {}
    for override in interface_overrides(values):
        for name, fields in override.items():
            resolved.setdefault(name, {}).update(fields)
    assert resolved["FurnitureEnhance_Prepare"]["next"] == [
        "FurnitureEnhance_ScrollTop" if keep_sort else "FurnitureFilter_OpenSort"
    ]
    assert resolved["FurnitureEnhance_AfterStart"]["anchor"]["FurnitureEnhance_PostRound"] == (
        "FurnitureEnhance_ReturnForRequest" if auto_request else "FurnitureEnhance_RoundComplete"
    )
    assert resolved["FurnitureSchedule_Permit"]["max_hit"] == 1


@pytest.mark.parametrize("mode", ["fixed", "shortest", "longest"])
def test_native_ordered_interface_overrides_preserve_mode_and_interval(native, mode):
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
