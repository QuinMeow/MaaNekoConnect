import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import run_soleil_upgrade as runner


ROOT = Path(__file__).resolve().parents[1]


def detail(*names):
    nodes = []
    for item in names:
        name, completed = item if isinstance(item, tuple) else (item, True)
        nodes.append(SimpleNamespace(name=name, completed=completed))
    return SimpleNamespace(nodes=nodes)


def recovery_trace():
    return ["CommonRecoveryEnter", "CommonRecoveryDispatch", "CommonRecoveryRecovered"]


@pytest.fixture
def framework(monkeypatch):
    import maa.controller
    import maa.resource
    import maa.tasker
    import maa.toolkit

    resource, controller, tasker = Mock(), Mock(), Mock(inited=True)
    device = SimpleNamespace(address="127.0.0.1:5557")
    toolkit = Mock(find_adb_devices=Mock(return_value=[device]))
    job = Mock(done=True, succeeded=True, get=Mock(return_value=detail("FurnitureEnhance_Complete")))
    job.wait.return_value = job
    tasker.post_task.return_value = job
    resource.post_bundle.return_value = controller.post_connection.return_value = job
    for module, name, value in ((maa.resource, "Resource", lambda: resource),
                                (maa.controller, "AdbController", lambda **kwargs: controller),
                                (maa.tasker, "Tasker", Mock(return_value=tasker)),
                                (maa.toolkit, "Toolkit", toolkit)):
        monkeypatch.setattr(module, name, value)
    for module, name in (("recovery", "register_recovery"), ("furniture_timer", "register_furniture_timer")):
        monkeypatch.setattr(f"{module}.{name}", Mock())
    monkeypatch.setattr(runner, "controller_options", lambda found: {"address": found.address})
    monkeypatch.setattr(runner, "connect_adb", Mock())
    monkeypatch.setattr(runner, "ensure_package_installed", Mock())
    monkeypatch.setattr(sys, "path", sys.path.copy())
    return SimpleNamespace(tasker=tasker, toolkit=toolkit, job=job)


@pytest.mark.parametrize("argv", [[], ["--execute", "--max-starts", "6"],
                                 ["--execute", "--wait-mode", "single", "--rounds", "2"],
                                 ["--execute", "--all-furniture"]])
def test_invalid_cli_never_resolves_adb(monkeypatch, argv):
    monkeypatch.setattr(runner, "resolve_adb_path", lambda value: pytest.fail("ADB lookup"))
    with pytest.raises(SystemExit) as error:
        runner.main(argv)
    assert error.value.code == 2


def test_direct_run_requires_explicit_spending_consent(framework):
    with pytest.raises(ValueError, match="--execute"):
        runner.run(ROOT, Path("adb.exe"))
    runner.connect_adb.assert_not_called()


def test_authorized_run_has_finite_budgets_and_never_falls_back(framework):
    assert runner.run(ROOT, Path("adb.exe"), execute=True, rounds=3) == 0
    runner.connect_adb.assert_called_once_with(Path("adb.exe"), "127.0.0.1:5557")
    entry, overrides = framework.tasker.post_task.call_args.args
    assert entry == "FurnitureSchedule_Start"
    assert overrides["FurnitureSchedule_Permit"]["max_hit"] == 3
    assert overrides["FurnitureEnhance_SessionSpendPermit"]["max_hit"] == 15
    framework.toolkit.find_adb_devices.return_value = [SimpleNamespace(address="127.0.0.1:5555")]
    framework.tasker.post_task.reset_mock()
    with pytest.raises(RuntimeError, match="5557"):
        runner.run(ROOT, Path("adb.exe"), execute=True)
    framework.tasker.post_task.assert_not_called()


@pytest.mark.parametrize("error", [RuntimeError("failed"), KeyboardInterrupt()])
def test_failed_or_interrupted_tasks_stop_without_retry(framework, error):
    framework.job.get.side_effect = error
    with pytest.raises(type(error)):
        runner.run(ROOT, Path("adb.exe"), execute=True)
    framework.tasker.post_task.assert_called_once()
    framework.tasker.post_stop.assert_called_once()


@pytest.mark.parametrize("names,count", [
    (["FurnitureEnhance_Complete"], 0),
    (["FurnitureEnhance_Start1", "FurnitureEnhance_Started", "FurnitureEnhance_Start1",
      "FurnitureEnhance_Started", "FurnitureEnhance_Complete"], 2),
    ([("", False), *recovery_trace(), "FurnitureEnhance_Complete"], 0),
])
def test_audit_counts_attempts_not_distinct_slots_and_allows_completed_recovery(names, count):
    assert runner.audit_fill_pass(detail(*names)) == count


@pytest.mark.parametrize("names", [
    [], ["FurnitureEnhance_StopCapture"], ["FurnitureEnhance_Started", "FurnitureEnhance_Complete"],
    ["FurnitureEnhance_Start1", "FurnitureEnhance_Complete"],
    ["FurnitureEnhance_Start1", *recovery_trace(), "FurnitureEnhance_Complete"],
    ["FurnitureEnhance_Start1", *recovery_trace(), "FurnitureEnhance_Started", "FurnitureEnhance_Complete"],
    ["CommonRecoveryEnter", "CommonStopGame", "FurnitureEnhance_Complete"],
    ["CommonRecoveryRecovered", "FurnitureEnhance_Complete"],
    ["CommonRecoveryEnter", *recovery_trace(), "FurnitureEnhance_Complete"],
    ["Soleil_RequestSupport", "FurnitureEnhance_Complete"],
    ["FurnitureEnhance_Start6", "FurnitureEnhance_Complete"],
    ["FurnitureEnhance_Complete", "FurnitureEnhance_Complete"],
])
def test_audit_rejects_unconfirmed_spending_incomplete_recovery_and_premature_requests(names):
    with pytest.raises(RuntimeError):
        runner.audit_fill_pass(detail(*names))


@pytest.mark.parametrize("node", ["FurnitureEnhance_Start1", "FurnitureEnhance_SessionSpendPermit"])
def test_recovery_never_refunds_total_or_per_round_budget(node):
    attempt = [node, "FurnitureEnhance_Started"] if node.endswith("Start1") else [node]
    names = [*attempt, *recovery_trace(), *attempt, "FurnitureEnhance_Complete"]
    with pytest.raises(RuntimeError, match="budget"):
        runner.audit_fill_pass(detail(*names), max_starts=1)
    with pytest.raises(RuntimeError, match="budget"):
        runner.audit_fill_pass(detail(*attempt * 6, "FurnitureEnhance_Complete"), max_starts=10)


def test_request_happens_once_after_a_productive_round_and_round_budget_is_shared():
    round_nodes = ["FurnitureEnhance_BeginRound", "FurnitureEnhance_Start1", "FurnitureEnhance_Started",
                   "FurnitureEnhance_RoundFinish", "Soleil_RequestSupport", "FurnitureEnhance_RoundComplete"]
    assert runner.audit_fill_pass(detail(*round_nodes * 2, "FurnitureSchedule_Complete"), rounds=2) == 2
    for names in ([*round_nodes[:-1], "Soleil_RequestSupport", "FurnitureEnhance_Complete"],
                  [*round_nodes * 2, "FurnitureSchedule_Complete"]):
        with pytest.raises(RuntimeError):
            runner.audit_fill_pass(detail(*names))
