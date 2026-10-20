import argparse
import re
import sys
import time
from pathlib import Path

from run_launch_capture import (
    DEFAULT_ADDRESS,
    connect_adb,
    controller_options,
    ensure_package_installed,
    find_exact_device,
    resolve_adb_path,
    wait_job,
)


ENTRY = "FurnitureSchedule_Start"
PASS_COMPLETE = "FurnitureEnhance_Complete"
COMPLETE_NODES = frozenset({PASS_COMPLETE, "FurnitureSchedule_Complete"})
RECOVERY_ENTRIES = frozenset({
    "CommonRecoveryEnter", "CommonRecoveryFrozenEnter", "CommonRecoveryHomeStallEnter"
})
RECOVERY_COMPLETE = "CommonRecoveryRecovered"
RECOVERY_ACTIONS = frozenset({
    "CommonNetworkConfirm", "CommonTitleTap", "CommonFrozen30", "CommonFrozenLoading",
    "CommonStopGame", "CommonStartGame",
})
RECOVERY_FATAL = frozenset({"CommonRecoveryStopCapture", "CommonRecoveryStop"})


def _validate_budget(one_pass, max_starts, rounds=1):
    if type(one_pass) is not bool:
        raise ValueError("one_pass must be a bool")
    if max_starts is not None and (type(max_starts) is not int or not 1 <= max_starts <= 5):
        raise ValueError("max_starts must be an integer from 1 to 5")
    if type(rounds) is not int or not 1 <= rounds <= 10000:
        raise ValueError("rounds must be an integer from 1 to 10000")
    if one_pass and rounds != 1:
        raise ValueError("--one-pass (or --one-batch) requires one round")
    return 5 * rounds if max_starts is None else max_starts


def _is_recovery_node(name):
    return name.startswith("CommonRecovery") or name in RECOVERY_ACTIONS


def _recovery_end(nodes, start):
    if start >= len(nodes) or getattr(nodes[start], "name", None) not in RECOVERY_ENTRIES:
        raise RuntimeError("Soleil fill pass failure was not followed immediately by recovery.")
    for index in range(start, len(nodes)):
        node = nodes[index]
        name = getattr(node, "name", "")
        if (
            not isinstance(name, str) or not _is_recovery_node(name)
            or name in RECOVERY_FATAL or getattr(node, "completed", False) is not True
            or (index != start and name in RECOVERY_ENTRIES)
        ):
            raise RuntimeError("Soleil fill pass contains an incomplete or interrupted recovery.")
        if name == RECOVERY_COMPLETE:
            return index
    raise RuntimeError("Soleil fill pass recovery has no completion marker.")


def audit_fill_pass(detail, *, max_starts=5, rounds=1):
    _validate_budget(False, None, rounds)
    if type(max_starts) is not int or not 1 <= max_starts <= 50000:
        raise ValueError("max_starts must be an integer from 1 to 50000")
    nodes = getattr(detail, "nodes", None)
    if not nodes or getattr(nodes[-1], "name", None) not in COMPLETE_NODES:
        raise RuntimeError("Soleil fill pass stopped without its completion marker.")

    pending_slot = None
    pending_recovered = False
    unconfirmed_recovery = False
    started_count = 0
    permit_count = 0
    round_starts = round_permits = round_acks = request_count = 0
    round_count = schedule_permits = 0
    round_finished = False
    round_closing = False
    index = 0
    while index < len(nodes):
        node = nodes[index]
        name = getattr(node, "name", "")
        completed = getattr(node, "completed", None)
        if not isinstance(name, str) or name in ("FurnitureEnhance_StopCapture", "SoleilStopCapture"):
            raise RuntimeError("Soleil fill pass contains an incomplete or error node.")
        if name in COMPLETE_NODES and index != len(nodes) - 1:
            raise RuntimeError("Soleil fill pass continued after its completion marker.")
        start = re.fullmatch(r"FurnitureEnhance_Start([1-5])", name)
        acknowledged = name == "FurnitureEnhance_Started"
        if name.startswith("FurnitureEnhance_Start") and not (start or acknowledged):
            raise RuntimeError("Soleil fill pass contains an unknown upgrade slot.")
        if start:
            if round_closing:
                raise RuntimeError("Soleil fill pass started again after its round was finished.")
            if pending_slot is not None and not pending_recovered:
                raise RuntimeError("Soleil fill pass started again before the previous acknowledgement.")
            pending_slot = start.group(1)
            pending_recovered = False
            started_count += 1
            round_starts += 1
            if round_starts > 5:
                raise RuntimeError("Soleil fill pass exceeded its per-round start budget.")
            if started_count > max_starts:
                raise RuntimeError("Soleil fill pass exceeded its authorized start budget.")
        if name == "FurnitureEnhance_SessionSpendPermit":
            permit_count += 1
            round_permits += 1
            if round_permits > 5:
                raise RuntimeError("Soleil fill pass exceeded its per-round permit budget.")
            if permit_count > max_starts:
                raise RuntimeError("Soleil fill pass exceeded its authorized permit budget.")

        if name in RECOVERY_ENTRIES or completed is False:
            if _is_recovery_node(name) and name not in RECOVERY_ENTRIES:
                raise RuntimeError("Soleil fill pass cannot recover a failed recovery node.")
            if name in RECOVERY_ENTRIES and completed is not True:
                raise RuntimeError("Soleil fill pass recovery entry did not complete.")
            recovery_start = index if name in RECOVERY_ENTRIES else index + 1
            # Native recognition timeouts have an empty name; only an adjacent,
            # complete recovery chain can account for this incomplete record.
            index = _recovery_end(nodes, recovery_start) + 1
            if pending_slot is not None:
                pending_recovered = True
                unconfirmed_recovery = True
            continue

        if not name or completed is not True or _is_recovery_node(name):
            raise RuntimeError("Soleil fill pass contains an incomplete or orphaned recovery node.")
        if name == "FurnitureSchedule_Permit":
            schedule_permits += 1
            if schedule_permits > rounds:
                raise RuntimeError("Soleil fill pass exceeded its scheduled round budget.")
        if name == "FurnitureEnhance_BeginRound":
            round_count += 1
            if round_count > rounds:
                raise RuntimeError("Soleil fill pass exceeded its round budget.")
            if round_count > 1 and not round_finished:
                raise RuntimeError("Soleil fill pass reset its round before completion.")
            round_starts = round_permits = round_acks = request_count = 0
            round_finished = False
            round_closing = False
        if name == "FurnitureEnhance_RoundFinish":
            round_closing = True
        if name == "Soleil_RequestSupport":
            request_count += 1
            if request_count > 1 or round_acks == 0 or not round_closing:
                raise RuntimeError("Soleil fill pass contains a repeated or premature support request.")
        if name == "FurnitureEnhance_RoundComplete":
            round_finished = True
        if acknowledged:
            if pending_slot is None:
                raise RuntimeError("Soleil fill pass has an unmatched upgrade acknowledgement.")
            pending_slot = None
            pending_recovered = False
            round_acks += 1
        index += 1

    if pending_slot is not None and not pending_recovered:
        raise RuntimeError("Soleil fill pass ended before confirming an upgrade started.")
    if unconfirmed_recovery:
        raise RuntimeError("Soleil fill pass: 恢复后仍有未确认强化结果。")
    return started_count


def run(
    project_root,
    adb_path,
    address=DEFAULT_ADDRESS,
    *,
    execute=False,
    one_pass=False,
    max_starts=None,
    use_existing_sort=True,
    sort_order="lv_asc",
    only_placed=True,
    only_upgradeable=True,
    auto_request=True,
    rounds=1,
    interval=60,
    wait_mode=None,
):
    if execute is not True:
        raise ValueError("Soleil upgrades spend game currency; pass --execute to run.")

    budget = _validate_budget(one_pass, max_starts, rounds)
    from soleil_options import build_schedule_overrides, build_soleil_overrides

    if wait_mode is None:
        wait_mode = "single" if rounds == 1 else "fixed"
    pipeline_override = build_schedule_overrides(rounds, interval, wait_mode)

    pipeline_override.update(build_soleil_overrides(
        use_existing_sort=use_existing_sort,
        sort_order=sort_order,
        only_placed=only_placed,
        only_upgradeable=only_upgradeable,
        auto_request=auto_request,
    ))
    pipeline_override["FurnitureEnhance_SessionSpendPermit"] = {"max_hit": budget}
    if budget <= 5:
        pipeline_override["FurnitureEnhance_RoundPermit5"] = {
            "next": ["FurnitureEnhance_SessionLimit"]
        }

    from maa.controller import AdbController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit

    project_root = Path(project_root).resolve()
    Toolkit.init_option(str(project_root))
    Tasker.set_save_on_error(True)
    connect_adb(adb_path, address)
    ensure_package_installed(adb_path, address)

    device = find_exact_device(Toolkit.find_adb_devices(str(adb_path)), address)
    controller = AdbController(**controller_options(device))
    resource = Resource()
    agent_path = str(project_root / "agent")
    if not sys.path or sys.path[0] != agent_path:
        sys.path.insert(0, agent_path)
    from recovery import register_recovery
    from furniture_timer import register_furniture_timer

    register_recovery(resource)
    register_furniture_timer(resource)
    wait_job(resource.post_bundle(str(project_root / "assets" / "resource")), "Resource load")
    wait_job(controller.post_connection(), "Device connection")

    tasker = Tasker()
    tasker.bind(resource, controller)
    if not tasker.inited:
        raise RuntimeError("Maa Tasker initialization failed")

    try:
        job = tasker.post_task(ENTRY, pipeline_override)
        # A native wait blocks signal handling during this unbounded task on Windows.
        while not job.done:
            time.sleep(0.2)
        wait_job(job, "Soleil upgrade task")
        # The error-capture terminal can succeed even when a gameplay guard failed.
        return audit_fill_pass(job.get(), max_starts=budget, rounds=rounds)
    except BaseException:
        tasker.post_stop().wait()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run one furniture refill round, or explicitly configure finite interval rounds."
    )
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--adb-path")
    parser.add_argument("--address", default=DEFAULT_ADDRESS)
    parser.add_argument(
        "--execute", action="store_true", help="Allow spending in-game upgrade currency."
    )
    parser.add_argument(
        "--one-pass", "--one-batch",
        dest="one_pass",
        action="store_true",
        help="Compatibility alias for the default single refill round (--one-batch is an alias).",
    )
    parser.add_argument(
        "--max-starts", type=int, choices=range(1, 6),
        help="Limit new starts across the entire task, including recovery and later rounds (1 to 5).",
    )
    parser.add_argument("--rounds", type=int, default=1, help="Total rounds, including the first (1 to 10000).")
    parser.add_argument("--interval", type=int, default=60, help="Fixed/fallback interval in seconds (10 to 86400).")
    parser.add_argument("--wait-mode", choices=["single", "fixed", "shortest", "longest"])
    parser.add_argument(
        "--configure-sort", action="store_true",
        help="Set sorting and filters instead of preserving the game's current settings.",
    )
    parser.add_argument("--sort-order", choices=["lv_asc", "lv_desc"])
    parser.add_argument("--all-furniture", action="store_true", help="Disable the placed-only filter.")
    parser.add_argument(
        "--include-unupgradeable", action="store_true", help="Disable the upgradeable-only filter."
    )
    parser.add_argument("--no-auto-request", action="store_true", help="Do not request once at the end of a productive round.")
    args = parser.parse_args(argv)
    if not args.execute:
        parser.error("--execute is required because this task spends in-game currency")
    try:
        _validate_budget(args.one_pass, args.max_starts, args.rounds)
        if not 10 <= args.interval <= 86400:
            raise ValueError("--interval must be from 10 to 86400 seconds")
        if args.wait_mode == "single" and args.rounds != 1:
            raise ValueError("--wait-mode single requires one round")
    except ValueError as error:
        parser.error(str(error))
    if not args.configure_sort and (
        args.sort_order is not None or args.all_furniture or args.include_unupgradeable
    ):
        parser.error("--sort-order, --all-furniture and --include-unupgradeable require --configure-sort")

    try:
        run(
            args.project_root,
            resolve_adb_path(args.adb_path),
            args.address,
            execute=True,
            one_pass=args.one_pass,
            max_starts=args.max_starts,
            use_existing_sort=not args.configure_sort,
            sort_order=args.sort_order or "lv_asc",
            only_placed=not args.all_furniture,
            only_upgradeable=not args.include_unupgradeable,
            auto_request=not args.no_auto_request,
            rounds=args.rounds,
            interval=args.interval,
            wait_mode=args.wait_mode,
        )
    except KeyboardInterrupt:
        print("Soleil upgrade task stopped; ADB server left running.", file=sys.stderr)
        return 130
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Soleil upgrade task failed: {error}", file=sys.stderr)
        return 1

    print("Soleil upgrade task finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
