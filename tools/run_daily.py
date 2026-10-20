"""Run explicitly selected independent daily modules once, without retries."""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from run_launch_capture import (
    DEFAULT_ADDRESS, connect_adb, controller_options, ensure_package_installed,
    find_exact_device, resolve_adb_path,
)


ROOT = Path(__file__).resolve().parents[1]
TASK_ENTRIES = {
    "login": "DailyLogin_Start",
    "income": "DailyIncome_Start", "friend": "DailyFriend_Start",
    "delivery": "DailyDelivery_Start", "gift": "DailyGift_Start",
    "vr": "DailyVR_Start", "contest": "DailyContest_Start",
    "exchange": "DailyExchange_Start", "gacha": "DailyGacha_Start",
    "mail": "DailyMail_Start", "guild": "DailyGuild_Start",
    "rewards": "DailyRewards_Start",
}
LEGACY_FLAGS = {"gold": "exchange", "new_delivery": "delivery", "gift": "gift", "locate_ad": "gacha"}
FINISHED = {"finished", "complete", "partial", "exhausted", "unavailable", "capacity_limited", "free_quota_consumed"}


def validate_timeout(timeout):
    if type(timeout) is not int or not 30 <= timeout <= 1800:
        raise ValueError("Timeout must be 30..1800 seconds")


def task_plan(tasks=None, *, inspect_only=False):
    if inspect_only:
        if tasks:
            raise ValueError("--inspect-only cannot be combined with --tasks")
        return [("inspect", "Daily_Start")]
    if not isinstance(tasks, (list, tuple)) or not tasks:
        raise ValueError("Choose explicit modules with --tasks, or use --inspect-only")
    if any(not isinstance(name, str) or name not in TASK_ENTRIES for name in tasks):
        raise ValueError("Unknown task; available --tasks: " + ", ".join(TASK_ENTRIES))
    if len(tasks) != len(set(tasks)):
        raise ValueError("Each task may appear only once")
    entries = [TASK_ENTRIES[name] for name in tasks]
    if len(entries) != len(set(entries)):
        raise ValueError("The same entry may not run twice")
    names = [name for name in tasks if name != "rewards"]
    if "rewards" in tasks:
        names.append("rewards")
    return [(name, TASK_ENTRIES[name]) for name in names]


def require_ocr_models(root):
    folder = Path(root) / "assets/resource/model/ocr"
    if not all((folder / name).is_file() and (folder / name).stat().st_size > 0
               for name in ("det.onnx", "rec.onnx", "keys.txt")):
        raise RuntimeError("Daily tasks require provisioned OCR models in assets/resource/model/ocr")


def inspection_overrides():
    names = ["Daily_Choose" + part for part in (
        "Income", "Friend", "Delivery", "VR", "Contest", "Gold", "Gift", "Gacha", "Mail", "Guild",
    )]
    names += ["Daily_Claim", "Daily_ClaimGate", "Daily_Milestone", "Daily_NewDelivery"]
    return {name: {"enabled": False} for name in names}


def summarize(detail, *, timed_out=False, observed_attempts=None):
    names = [item.name for item in detail.nodes] if detail else []
    completion = "unverified"
    result = "stopped"
    if "DailyCore_Recover" in names or "CommonRecoveryRecovered" in names:
        result = "recovered_unverified"
    elif "DailyGacha_AdUnavailable" in names:
        result = "unavailable"
    elif "Daily_CompleteHome" in names:
        result, completion = "complete", "confirmed"
    elif "Daily_PartialHome" in names:
        result, completion = "partial", "incomplete"
    elif "DailyCore_Done" in names:
        result = "finished"
        if "DailyGacha_AdQuotaConsumed" in names:
            result = "free_quota_consumed"
        elif "DailyVR_Unavailable" in names:
            result = "unavailable"
        elif any(name in names for name in ("DailyVR_Exhausted", "DailyGift_Exhausted")):
            result = "exhausted"
        elif any(name in names for name in ("DailyMail_CapacityGate", "DailyMail_CapacityClose")):
            result = "capacity_limited"
    if timed_out:
        result, completion = "timeout", "unverified"
    attempts = ([name for name in names if name.endswith("Spend")]
                if observed_attempts is None else list(observed_attempts))
    return {"result": result, "game_completion": completion, "address": DEFAULT_ADDRESS,
            "nodes": names, "attempted": attempts,
            "note": "Module finish or action start is not proof of game completion. Never replay uncertain spending."}


def wait_until_done(job, deadline):
    while not job.done:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)
    return True


def stop_bounded(tasker):
    return wait_until_done(tasker.post_stop(), time.monotonic() + 5)


def execute_tasks(tasker, tasks, timeout, attempts, *, inspect_only=False, on_result=None):
    validate_timeout(timeout)
    plan = task_plan(tasks, inspect_only=inspect_only)
    deadline, results, halted = time.monotonic() + timeout, [], None
    for name, entry in plan:
        if halted:
            results.append({"task": name, "entry": entry, "result": "not_run",
                            "game_completion": "unverified", "attempted": [], "nodes": []})
            continue
        offset, started_at, job = len(attempts), time.time(), None
        timed_out, interrupted, error, stop_completed = False, False, None, None
        observed = None
        try:
            if time.monotonic() >= deadline:
                timed_out = True
            else:
                job = tasker.post_task(entry, inspection_overrides() if inspect_only else {})
                if not wait_until_done(job, deadline):
                    timed_out, stop_completed = True, stop_bounded(tasker)
                observed = job.get()
        except KeyboardInterrupt:
            interrupted, stop_completed = True, stop_bounded(tasker)
        except Exception as exc:
            error, stop_completed = type(exc).__name__, stop_bounded(tasker)
        item = summarize(observed, timed_out=timed_out, observed_attempts=attempts[offset:])
        if (name == "login" and item["result"] == "recovered_unverified"
                and item["nodes"][-1:] == ["DailyCore_Done"] and not item["attempted"]
                and not any(node.endswith("Spend") for node in item["nodes"])
                and "CommonStopGame" not in item["nodes"]):
            item.update(result="finished", login_recovered_to_home=True)
        item.update(task=name, entry=entry, started_at=started_at)
        if interrupted:
            item.update(result="interrupted", game_completion="unverified")
        if error:
            item.update(result="stopped", game_completion="unverified", error=error)
        if job is not None:
            item["job_succeeded"] = bool(job.succeeded)
            if not job.succeeded and item["result"] in FINISHED and item["result"] != "unavailable":
                item["result"] = "stopped"
        if stop_completed is not None:
            item["stop_completed"] = stop_completed
        results.append(item)
        if on_result is not None:
            on_result(item, len(results))
        if item["result"] not in FINISHED or (job is not None and not job.succeeded):
            halted = item["result"]
    result = halted or ("partial" if any(item["result"] in {"partial", "unavailable", "capacity_limited"}
                                        for item in results) else results[-1]["result"])
    if result == "exhausted":
        result = "finished"
    return {"result": result, "address": DEFAULT_ADDRESS, "tasks": results,
            "game_completion": "unverified" if halted else results[-1]["game_completion"],
            "attempted": list(attempts), "nodes": [node for item in results for node in item["nodes"]],
            "note": "Selected entries run at most once. finished is execution status, not all daily conditions."}


def new_report_folder():
    folder = ROOT / "debug/daily-runs" / f"{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}_{time.time_ns()}"
    folder.mkdir(parents=True, exist_ok=False)
    return folder


def archive_artifacts(folder, started_at, prefix=""):
    sources = list((ROOT / "debug/screencap").glob("daily*.png"))
    sources += [ROOT / "debug/screencap/common_recovery_stopped.png"]
    artifacts = []
    for source in sorted(sources):
        if source.is_file() and source.stat().st_mtime >= started_at:
            target = folder / (prefix + source.name)
            shutil.copy2(source, target)
            artifacts.append(str(target))
    return artifacts


def save_report(report, started_at, folder=None):
    folder = new_report_folder() if folder is None else folder
    if "artifacts" not in report:
        report["artifacts"] = archive_artifacts(folder, started_at)
    report["report_path"] = str(folder / "report.json")
    data = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    (folder / "report.json").write_text(data, encoding="utf-8")
    (ROOT / "debug/daily_report.json").write_text(data, encoding="utf-8")
    return report


def run(adb_path, tasks=None, timeout=600, *, inspect_only=False):
    validate_timeout(timeout)
    task_plan(tasks, inspect_only=inspect_only)
    require_ocr_models(ROOT)
    from maa.context import ContextEventSink
    from maa.controller import AdbController
    from maa.resource import Resource
    from maa.tasker import Tasker as MaaTasker
    from maa.toolkit import Toolkit
    from maa.event_sink import NotificationType

    sys.path.insert(0, str(ROOT))
    from agent.ad_close import register_ad_close
    from agent.recovery import register_recovery
    from agent.delivery import register_delivery
    from agent.login import register_login

    Toolkit.init_option(str(ROOT))
    connect_adb(adb_path, DEFAULT_ADDRESS)
    ensure_package_installed(adb_path, DEFAULT_ADDRESS)
    device = find_exact_device(Toolkit.find_adb_devices(str(adb_path)), DEFAULT_ADDRESS)
    controller, resource = AdbController(**controller_options(device)), Resource()
    register_recovery(resource)
    register_delivery(resource)
    register_ad_close(resource)
    register_login(resource)
    for job, label in ((resource.post_bundle(ROOT / "assets/resource"), "Resource load"),
                       (controller.post_connection(), "Controller connection")):
        if not wait_until_done(job, time.monotonic() + 30) or not job.succeeded:
            raise RuntimeError(label + " failed or exceeded 30 seconds")
    tasker = MaaTasker()
    if not tasker.bind(resource, controller) or not tasker.inited:
        raise RuntimeError("Tasker initialization failed")
    attempts = []

    class Audit(ContextEventSink):
        def on_node_action(self, context, noti_type, detail):
            if noti_type == NotificationType.Starting and detail.name.endswith("Spend"):
                attempts.append(detail.name)

    audit = Audit()
    if tasker.add_context_sink(audit) is None:
        raise RuntimeError("Could not attach consumption-attempt audit")
    started_at, folder = time.time(), new_report_folder()

    def record(item, index):
        item["artifacts"] = archive_artifacts(folder, item["started_at"], f"{index:02}_{item['task']}_")

    report = execute_tasks(tasker, tasks, timeout, attempts, inspect_only=inspect_only, on_result=record)
    report["options"] = {"requested_tasks": list(tasks or []), "inspect_only": inspect_only, "timeout": timeout}
    report["artifacts"] = [path for item in report["tasks"] for path in item.get("artifacts", [])]
    return save_report(report, started_at, folder)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb-path", required=True)
    parser.add_argument("--tasks", nargs="+", metavar="TASK", help=", ".join(TASK_ENTRIES))
    parser.add_argument("--inspect-only", action="store_true")
    parser.add_argument("--timeout", type=int, default=600)
    for flag in LEGACY_FLAGS:
        parser.add_argument("--" + flag.replace("_", "-"), action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    legacy = [flag for flag in LEGACY_FLAGS if getattr(args, flag)]
    if legacy:
        parser.error("Legacy switches are retired; use --tasks " + " ".join(LEGACY_FLAGS[flag] for flag in legacy))
    try:
        validate_timeout(args.timeout)
        task_plan(args.tasks, inspect_only=args.inspect_only)
    except ValueError as exc:
        parser.error(str(exc))
    report = run(resolve_adb_path(args.adb_path), args.tasks, args.timeout, inspect_only=args.inspect_only)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["result"] in {"complete", "finished", "free_quota_consumed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
