from pathlib import Path
from types import SimpleNamespace
import time

import pytest

import run_daily


def detail(*names):
    return SimpleNamespace(nodes=[SimpleNamespace(name=name) for name in names])


class Tasker:
    def __init__(self, traces, attempts=None, running=False, succeeded=True):
        self.traces, self.attempts, self.running = list(traces), attempts, running
        self.succeeded = succeeded
        self.calls, self.stops = [], 0

    def post_task(self, entry, overrides):
        self.calls.append((entry, overrides))
        names = self.traces.pop(0)
        if self.attempts is not None:
            self.attempts.extend(name for name in names if name.endswith("Spend"))
        return SimpleNamespace(done=not self.running, succeeded=self.succeeded, get=lambda: detail(*names))

    def post_stop(self):
        self.stops += 1
        return SimpleNamespace(done=True)


def test_plan_preserves_chosen_order_and_places_only_explicit_rewards_last():
    plan = run_daily.task_plan(["rewards", "friend", "income"])
    assert [name for name, _ in plan] == ["friend", "income", "rewards"]
    assert plan[-1][1] == "DailyRewards_Start"
    assert run_daily.task_plan(["vr"]) == [("vr", "DailyVR_Start")]


@pytest.mark.parametrize("tasks", [[], ["unknown"], ["friend", "friend"], "income"])
def test_empty_unknown_and_duplicate_tasks_fail_closed(tasks):
    with pytest.raises(ValueError):
        run_daily.task_plan(tasks)


def test_alias_cannot_execute_the_same_entry_twice(monkeypatch):
    monkeypatch.setitem(run_daily.TASK_ENTRIES, "alias", run_daily.TASK_ENTRIES["income"])
    with pytest.raises(ValueError, match="entry"):
        run_daily.task_plan(["income", "alias"])


def test_inspection_remains_legacy_read_only_and_cannot_mix_with_work():
    assert run_daily.task_plan(None, inspect_only=True) == [("inspect", "Daily_Start")]
    with pytest.raises(ValueError):
        run_daily.task_plan(["income"], inspect_only=True)
    overrides = run_daily.inspection_overrides()
    for name in ("Daily_ClaimGate", "Daily_Claim", "Daily_Milestone", "Daily_NewDelivery",
                 "Daily_ChooseIncome", "Daily_ChooseGift", "Daily_ChooseGacha"):
        assert overrides[name] == {"enabled": False}
    assert not any("max_hit" in value for value in overrides.values())


@pytest.mark.parametrize("names,result,completion", [
    ([], "stopped", "unverified"), (["DailyCore_Done"], "finished", "unverified"),
    (["Daily_CompleteCapture"], "stopped", "unverified"),
    (["Daily_CompleteHome"], "complete", "confirmed"),
    (["Daily_PartialHome"], "partial", "incomplete"),
    (["DailyMail_CapacityClose", "DailyCore_Done"], "capacity_limited", "unverified"),
    (["DailyCore_Recover", "DailyCore_Done"], "recovered_unverified", "unverified"),
    (["DailyGacha_AdUnavailable", "Daily_Stop"], "unavailable", "unverified"),
    (["DailyGacha_AdQuotaConsumed", "DailyCore_Done"], "free_quota_consumed", "unverified"),
])
def test_report_does_not_confuse_framework_or_module_finish_with_game_completion(names, result, completion):
    report = run_daily.summarize(detail(*names))
    assert report["result"] == result and report["game_completion"] == completion
    assert report["address"] == "127.0.0.1:5557"
    assert run_daily.summarize(detail(*names), timed_out=True)["result"] == "timeout"


def test_selected_entries_run_once_and_rewards_run_last():
    tasker = Tasker([["DailyCore_Done"]] * 3)
    report = run_daily.execute_tasks(tasker, ["rewards", "friend", "income"], 60, [])
    assert [entry for entry, _ in tasker.calls] == [
        "DailyFriend_Start", "DailyIncome_Start", "DailyRewards_Start"]
    assert all(overrides == {} for _, overrides in tasker.calls)
    assert report["result"] == "finished" and report["game_completion"] == "unverified"
    assert len(report["tasks"]) == 3 and tasker.stops == 0


def test_failure_keeps_attempt_audit_and_never_runs_or_retries_remaining_entries():
    attempts = []
    tasker = Tasker([["DailyCore_Done"], ["DailyVR_SkipSpend", "Daily_Stop"]], attempts)
    report = run_daily.execute_tasks(tasker, ["income", "vr", "rewards"], 60, attempts)
    assert len(tasker.calls) == 2
    assert report["result"] == "stopped" and report["tasks"][-1]["result"] == "not_run"
    assert report["attempted"] == ["DailyVR_SkipSpend"]
    assert report["tasks"][1]["attempted"] == report["attempted"]


def test_framework_success_alone_stops_the_sequence():
    tasker = Tasker([[]])
    report = run_daily.execute_tasks(tasker, ["income", "friend"], 60, [])
    assert report["result"] == "stopped" and len(tasker.calls) == 1


def test_timeout_requests_bounded_stop_and_does_not_start_next_task(monkeypatch):
    clock = iter(range(0, 1000, 10))
    monkeypatch.setattr(run_daily.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(run_daily.time, "sleep", lambda _: None)
    tasker = Tasker([["DailyVR_SkipSpend"]], running=True)
    report = run_daily.execute_tasks(tasker, ["vr", "rewards"], 30, ["DailyVR_SkipSpend"])
    assert report["result"] == "timeout" and tasker.stops == 1 and len(tasker.calls) == 1
    assert report["tasks"][-1]["result"] == "not_run"


def test_a_stuck_stop_job_has_a_finite_wait_without_calling_blocking_wait(monkeypatch):
    clock = iter([0, 3, 6])
    monkeypatch.setattr(run_daily.time, "monotonic", lambda: next(clock))
    monkeypatch.setattr(run_daily.time, "sleep", lambda _: None)
    tasker = SimpleNamespace(post_stop=lambda: SimpleNamespace(done=False))
    assert run_daily.stop_bounded(tasker) is False


@pytest.mark.parametrize("timeout", [0, 29, 1801, True, "60"])
def test_invalid_timeout_fails_before_posting_any_task(timeout):
    tasker = Tasker([])
    with pytest.raises(ValueError):
        run_daily.execute_tasks(tasker, ["income"], timeout, [])
    assert not tasker.calls


@pytest.mark.parametrize("flag", ["--gold", "--new-delivery", "--gift", "--locate-ad"])
def test_legacy_flags_have_an_explicit_migration_error_before_device_access(flag, capsys):
    with pytest.raises(SystemExit) as error:
        run_daily.main(["--adb-path", "unused", flag])
    assert error.value.code == 2 and "--tasks" in capsys.readouterr().err


def test_action_start_survives_missing_completed_nodes():
    report = run_daily.summarize(None, observed_attempts=["DailyGacha_AdSpend"])
    assert report["result"] == "stopped" and report["attempted"] == ["DailyGacha_AdSpend"]


def test_reports_keep_history_and_do_not_reuse_stale_screenshots(tmp_path, monkeypatch):
    monkeypatch.setattr(run_daily, "ROOT", tmp_path)
    capture = tmp_path / "debug/screencap/daily_complete.png"
    capture.parent.mkdir(parents=True)
    capture.write_bytes(b"old screenshot")
    first = run_daily.save_report({"result": "finished"}, time.time() + 1)
    second = run_daily.save_report({"result": "finished"}, 0)
    assert not first["artifacts"] and second["artifacts"]
    assert first["report_path"] != second["report_path"]
    assert Path(first["report_path"]).is_file() and Path(second["report_path"]).is_file()


def test_missing_or_empty_ocr_models_fail_before_device_operations(tmp_path):
    with pytest.raises(RuntimeError, match="OCR"):
        run_daily.require_ocr_models(tmp_path)
    folder = tmp_path / "assets/resource/model/ocr"
    folder.mkdir(parents=True)
    for name in ("det.onnx", "rec.onnx", "keys.txt"):
        (folder / name).write_bytes(b"fixture")
    run_daily.require_ocr_models(tmp_path)
    (folder / "rec.onnx").write_bytes(b"")
    with pytest.raises(RuntimeError, match="OCR"):
        run_daily.require_ocr_models(tmp_path)


@pytest.mark.parametrize("names,status,success,call_count", [
    (["DailyCore_Recover", "DailyCore_Done"], "recovered_unverified", True, 1),
    (["DailyGacha_AdUnavailable", "Daily_Stop"], "unavailable", False, 1),
    (["DailyGacha_AdQuotaConsumed", "DailyCore_Done"], "free_quota_consumed", True, 2),
])
def test_recovery_and_failed_ad_stop_batch_without_claiming_draw_credit(names, status, success, call_count):
    tasker = Tasker([names, ["DailyCore_Done"]], succeeded=success)
    report = run_daily.execute_tasks(tasker, ["gacha", "income"], 60, [])
    assert report["tasks"][0]["result"] == status
    assert report["tasks"][0]["game_completion"] == "unverified"
    assert len(tasker.calls) == call_count
    if call_count == 1:
        assert report["result"] == status and report["tasks"][1]["result"] == "not_run"


@pytest.mark.parametrize("task,marker,item_result,batch_result,code", [
    ("vr", "DailyVR_Exhausted", "exhausted", "finished", 0),
    ("gift", "DailyGift_Exhausted", "exhausted", "finished", 0),
    ("mail", "DailyMail_CapacityClose", "capacity_limited", "partial", 2),
])
def test_quota_exhaustion_is_normal_but_capacity_remains_partial(task, marker, item_result,
                                                               batch_result, code, monkeypatch):
    report = run_daily.execute_tasks(Tasker([[marker, "DailyCore_Done"]]), [task], 60, [])
    assert report["tasks"][0]["result"] == item_result
    assert report["result"] == batch_result and report["game_completion"] == "unverified"
    monkeypatch.setattr(run_daily, "run", lambda *args, **kwargs: report)
    monkeypatch.setattr(run_daily, "resolve_adb_path", lambda _: Path("offline-adb"))
    assert run_daily.main(["--adb-path", "offline", "--tasks", task]) == code
