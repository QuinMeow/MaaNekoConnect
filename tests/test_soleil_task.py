import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MODULES = ("Delivery", "Bath", "Duty", "Furniture")


def options(values=None):
    interface = json.loads((ROOT / "assets/interface.json").read_text("utf-8"))
    values, patches = values or {}, []

    def resolve(name):
        item = interface["option"][name]
        if item["type"] == "input":
            text = json.dumps(item["pipeline_override"])
            for field in item["inputs"]:
                value = str(values.get(field["name"], field["default"]))
                text = text.replace('"{' + field["name"] + '}"', value)
            patches.append(json.loads(text))
            return
        selected = values.get(name, item["default_case"])
        selected = selected if isinstance(selected, list) else [selected]
        for case in item["cases"]:
            if case["name"] in selected:
                patches.append(case.get("pipeline_override", {}))
                for child in case.get("option", []):
                    resolve(child)

    task = next(task for task in interface["task"] if task["name"] == "Soleil")
    for name in task["option"]:
        resolve(name)
    return interface, patches


def simulated(pipelines):
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 1, "rate_limit": 0}
             for name in pipelines}
    graph = {"DailyDelivery_Start": ["DailyCore_Done"], "DailyCore_Done": [],
             "NavSoleil_Ensure": ["[Anchor]NavSoleil_Return"],
             "Soleil_BathOpen": ["Soleil_BathComplete"],
             "Soleil_DutyOpen": ["Soleil_DutyComplete"],
             "FurnitureSchedule_Start": ["FurnitureSchedule_Complete"],
             "FurnitureSchedule_Complete": [],
             "NavHome_Normalize": ["[Anchor]NavHome_NormalizeReturn"]}
    for name, targets in graph.items():
        patch[name].update(recognition="DirectHit", action="DoNothing", next=targets)
    return patch


def test_checkbox_preserves_nested_furniture_settings_and_refresh_is_opt_in():
    interface, patches = options({"SoleilModules": list(MODULES), "FurnitureSchedule": "longest",
                                  "Rounds": 3, "Seconds": 90, "UseExistingSort": "No"})
    assert interface["option"]["SoleilModules"]["default_case"] == ["Delivery", "Bath", "Duty"]
    assert interface["option"]["DailyDeliveryPaidRefresh"]["default_case"] == "No"
    assert not {"DailyDelivery_Start", "FurnitureSchedule_Start"} & {
        task["entry"] for task in interface["task"]}
    resolved = {}
    for patch in patches:
        for name, fields in patch.items():
            resolved.setdefault(name, {}).update(fields)
    assert resolved["FurnitureTimer_Config"]["custom_action_param"] == {"op": "config", "mode": "longest"}
    assert resolved["FurnitureTimer_IntervalConfig"]["custom_action_param"] == {"op": "interval", "seconds": 90}
    assert resolved["FurnitureSchedule_Permit"]["max_hit"] == 3
    assert resolved["FurnitureEnhance_Prepare"]["next"] == ["FurnitureFilter_OpenSort"]
    assert not resolved["DailyDelivery_PaidRefreshPermit"]["enabled"]


@pytest.mark.parametrize("selected", [[], *[[name] for name in MODULES], list(MODULES), None])
def test_native_selected_modules_run_once_in_order_and_return_home(native, pipelines, selected):
    values = {} if selected is None else {"SoleilModules": selected}
    _, patches = options(values)
    detail = native.run("Soleil_DailyStart", [simulated(pipelines), *patches])
    names = [node.name for node in detail.nodes]
    expected = [module for module in MODULES if module in (selected if selected is not None else MODULES[:3])]
    assert [module for name in names for module in MODULES if name == f"Soleil_{module}Run"] == expected
    assert names[-1] == "Soleil_Done" and names.count("Soleil_Done") == 1
    assert names.count("DailyDelivery_Start") == ("Delivery" in expected)
    assert names.count("FurnitureSchedule_Start") == ("Furniture" in expected)
    assert "NavHome_Normalize" in names


def test_native_empty_selection_on_home_needs_no_clicks(native, frame, pipelines):
    native.controller.image = frame("navigation", "home_ready", {
        "home_building": (535, 1105, 140, 110), "home_label": (530, 1205, 155, 65)})
    _, patches = options({"SoleilModules": []})
    timing = {name: {"post_delay": 0, "timeout": 50, "rate_limit": 1} for name in pipelines}
    names = [node.name for node in native.run("Soleil_DailyStart", [timing, *patches]).nodes]
    assert names[-1] == "Soleil_Done" and "NavHome_Normalized" in names
    assert not any(name.endswith("Run") for name in names)


@pytest.mark.parametrize("module,unconfirmed", [("Bath", False), ("Bath", True), ("Duty", True)])
def test_native_child_stop_or_unconfirmed_result_cannot_run_later_modules(native, pipelines, module, unconfirmed):
    _, patches = options({"SoleilModules": list(MODULES)})
    patch = simulated(pipelines)
    patch[f"Soleil_{module}Open"]["next"] = [f"Soleil_{module}Unconfirmed" if unconfirmed else "Soleil_Stop"]
    patch[f"Soleil_{module}Return"].update(recognition="DirectHit", action="DoNothing",
                                         next=[f"Soleil_{module}Complete"])
    names = [node.name for node in native.run("Soleil_DailyStart", [patch, *patches]).nodes]
    assert names.count("DailyDelivery_Start") == 1 and names[-1] == "Soleil_Stop"
    assert ("NavHome_Normalize" in names) is unconfirmed
    assert f"Soleil_{module}Complete" not in names and "Soleil_Done" not in names
    assert not any(f"Soleil_{later}Run" in names for later in MODULES[MODULES.index(module) + 1:])


def test_free_and_paid_delivery_refresh_can_only_be_enabled_with_delivery_selected():
    _, disabled = options({"SoleilModules": [], "DailyDeliveryPaidRefresh": "Yes"})
    assert not any("DailyDelivery_PaidRefreshPermit" in patch for patch in disabled)
    _, enabled = options({"SoleilModules": ["Delivery"], "DailyDeliveryPaidRefresh": "Yes"})
    assert any(patch.get("DailyDelivery_PaidRefreshPermit", {}).get("enabled") for patch in enabled)


@pytest.mark.parametrize("enabled,limit", [("No", 36), ("Yes", 54)])
def test_delivery_option_preserves_the_complete_dispatch_budget(pipelines, enabled, limit):
    interface, patches = options({"SoleilModules": ["Delivery"], "DailyDeliveryPaidRefresh": enabled})
    resolved = {name: dict(fields) for name, fields in pipelines.items()}
    for patch in patches:
        for name, fields in patch.items():
            resolved[name].update(fields)
    assert "待接入" not in interface["option"]["DailyDeliveryPaidRefresh"]["label"]
    for name in ("DailyDelivery_Select", "DailyDelivery_Auto", "DailyDelivery_Spend"):
        assert resolved[name]["max_hit"] == limit
    assert resolved["DailyDelivery_Spend"]["attach"] == {
        "max_dispatches": limit, "max_battery_each": 10000, "diamond_finish": False}


@pytest.mark.parametrize("enabled,limit", [("No", 36), ("Yes", 54)])
def test_native_delivery_budget_covers_each_dispatch_stage_without_refunding_on_recovery(
    native, pipelines, enabled, limit,
):
    _, patches = options({"SoleilModules": ["Delivery"], "DailyDeliveryPaidRefresh": enabled})
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 1, "rate_limit": 0}
             for name in pipelines}
    graph = {"DeliveryBudgetStart": ["DeliveryBudgetDispatch"],
             "DeliveryBudgetDispatch": ["DailyDelivery_Select", "DeliveryBudgetDone"],
             "DailyDelivery_Select": ["DailyDelivery_Auto"], "DailyDelivery_Auto": ["DailyDelivery_Spend"],
             "DailyDelivery_Spend": ["DeliveryBudgetRecoverOnce", "DeliveryBudgetDispatch"],
             "DeliveryBudgetRecoverOnce": ["CommonRecoveryRecovered"], "DeliveryBudgetDone": []}
    for name, targets in graph.items():
        patch.setdefault(name, {}).update(recognition="DirectHit", action="DoNothing", next=targets,
                                          pre_delay=0, post_delay=0, timeout=1, rate_limit=0)
    patch["DeliveryBudgetStart"]["anchor"] = {"CommonRecoveryResume": "DeliveryBudgetDispatch"}
    patch["DeliveryBudgetRecoverOnce"]["max_hit"] = 1
    names = [node.name for node in native.run("DeliveryBudgetStart", [patch, *patches]).nodes]
    assert names[-1] == "DeliveryBudgetDone" and names.count("CommonRecoveryRecovered") == 1
    for name in ("DailyDelivery_Select", "DailyDelivery_Auto", "DailyDelivery_Spend"):
        assert names.count(name) == limit


@pytest.mark.parametrize("module,start,complete", [
    ("Delivery", "DailyDelivery_Start", "DailyCore_Done"),
    ("Furniture", "FurnitureSchedule_Start", "FurnitureSchedule_Complete"),
])
def test_final_home_recovery_cannot_reenter_completed_business(native, pipelines, module, start, complete):
    _, patches = options({"SoleilModules": [module]})
    patch = simulated(pipelines)
    patch[start]["anchor"] = {**pipelines[start].get("anchor", {}),
                               "CommonRecoveryResume": "FinishedSoleilBusiness"}
    patch["FinishedSoleilBusiness"] = {"recognition": "DirectHit", "action": "DoNothing", "post_delay": 0}
    patch["NavHome_Normalize"]["next"] = ["CommonRecoveryRecovered"]
    names = [node.name for node in native.run("Soleil_DailyStart", [patch, *patches]).nodes]
    assert complete in names and "CommonRecoveryRecovered" in names
    assert "FinishedSoleilBusiness" not in names and names[-1] == "Soleil_Stop"
    assert names.count(start) == 1


@pytest.mark.parametrize("choice,count", [(None, 0), ("No", 0), ("Yes", 1)])
def test_native_paid_refresh_option_uses_one_chain_and_returns_after_its_new_batch(native, pipelines, choice, count):
    values = {"SoleilModules": ["Delivery"]}
    if choice is not None:
        values["DailyDeliveryPaidRefresh"] = choice
    _, patches = options(values)
    patch = simulated(pipelines)
    chain = ("DailyDelivery_PaidRefreshPermit", "DailyDelivery_OpenPaidRefresh",
             "DailyDelivery_PaidRefreshSpend", "DailyDelivery_PaidRefreshVerified")
    for name in (*chain, "DailyDelivery_RefreshCheck", "DailyDelivery_NoFreeRefresh",
                 "DailyDelivery_Scan", "DailyDelivery_AllStarted"):
        patch[name].update(recognition="DirectHit", action="DoNothing")
    for name in ("DailyDelivery_FreeRefreshPrepare", "Daily_PostError",
                 "DailyDelivery_CollectGate", "DailyDelivery_Select"):
        patch[name]["enabled"] = False
    patch["DailyDelivery_Start"].update(next=["DailyDelivery_RefreshCheck"], anchor={
        **pipelines["DailyDelivery_Start"]["anchor"], "CommonRecoveryResume": "PaidOptionRetry"})
    patch["Daily_Return"].update(recognition="DirectHit", action="DoNothing", next=["CommonRecoveryRecovered"])
    patch["PaidOptionRetry"] = {"recognition": "DirectHit", "post_delay": 0,
                                "next": ["DailyDelivery_PaidRefreshPermit", "PaidOptionDone"]}
    patch["PaidOptionDone"] = {"recognition": "DirectHit", "post_delay": 0}
    names = [node.name for node in native.run("DailyDelivery_Start", [patch, *patches]).nodes]
    assert names[-1] == "PaidOptionDone" and names.count("CommonRecoveryRecovered") == 1
    assert names.count("DailyDelivery_RefreshCheck") == names.count("Daily_Return") == 1
    for name in chain:
        assert names.count(name) == count
    if count:
        assert names.index(chain[-1]) < names.index("DailyDelivery_AllStarted") < names.index("Daily_Return")
