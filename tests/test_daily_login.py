from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from agent.login import ACTIVITY_COMMAND, DailyLoginAppState, register_login, resumed_package


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = "jp.goodsmile.nekoconne"


def home_image():
    image = np.zeros((1280, 720, 3), dtype=np.uint8)
    with np.load(ROOT / "tests/fixtures/recovery/home_ready_holdout.npz") as crops:
        for key, (x, y) in {"home_building": (535, 1105), "home_text": (530, 1205)}.items():
            crop = crops[key]
            image[y:y + crop.shape[0], x:x + crop.shape[1]] = crop
    return image


def fast(pipelines):
    patch = {name: {"pre_delay": 0, "post_delay": 0, "timeout": 80, "rate_limit": 1}
             for name in pipelines}
    patch["CommonRecoveryStopCapture"]["action"] = "DoNothing"
    patch["Daily_StopCapture"]["action"] = "DoNothing"
    return patch


def test_login_launches_from_desktop_then_does_not_relaunch_on_the_next_task(native, pipelines):
    native.controller.foreground_package = "com.android.launcher3"
    launched, stopped = [], []

    def start(package):
        launched.append(package)
        native.controller.foreground_package = PACKAGE
        native.controller.image = home_image()
        return True

    native.controller.on_start = start
    native.controller.on_stop = lambda package: stopped.append(package) or True
    for _ in range(2):
        names = [node.name for node in native.run("DailyLogin_Start", fast(pipelines)).nodes]
        assert names[-1] == "DailyCore_Done", names
    assert launched == [PACKAGE] and stopped == []


def test_foreground_game_on_an_unknown_page_is_not_restarted(native, pipelines):
    calls = []
    native.controller.on_start = lambda package: calls.append("start") or True
    native.controller.on_stop = lambda package: calls.append("stop") or True
    names = [node.name for node in native.run("DailyLogin_Start", fast(pipelines)).nodes]
    assert names[-1] == "Daily_Stop" and calls == []
    assert "DailyLogin_Foreground" in names and "DailyLogin_Launch" not in names


@pytest.mark.parametrize("succeeds", [False, True])
def test_failed_or_ineffective_start_is_attempted_once_without_force_stop(native, pipelines, succeeds):
    native.controller.foreground_package = "com.android.launcher3"
    starts, stops = [], []
    native.controller.on_start = lambda package: starts.append(package) or succeeds
    native.controller.on_stop = lambda package: stops.append(package) or True
    names = [node.name for node in native.run("DailyLogin_Start", fast(pipelines)).nodes]
    assert starts == [PACKAGE] and stops == []
    assert names[-1] == "Daily_Stop" and "DailyCore_Done" not in names


def test_unknown_foreground_stops_without_starting_or_restarting(native, pipelines):
    native.controller.foreground_package = None
    calls = []
    native.controller.on_start = lambda package: calls.append("start") or True
    native.controller.on_stop = lambda package: calls.append("stop") or True
    names = [node.name for node in native.run("DailyLogin_Start", fast(pipelines)).nodes]
    assert names[-1] == "Daily_Stop" and calls == []


@pytest.mark.parametrize("output,expected", [
    (f"topResumedActivity=ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}", PACKAGE),
    (f"mResumedActivity: ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}", PACKAGE),
    (f"ResumedActivity: ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}", PACKAGE),
    (f"topResumedActivity=ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}\n"
     f"ResumedActivity: ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}", PACKAGE),
    (f"Historical ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}\n"
     "topResumedActivity=ActivityRecord{abc u0 com.android.launcher3/.Launcher t2}", "com.android.launcher3"),
    (f"topResumedActivity=ActivityRecord{{abc u0 {PACKAGE}.other/.Main t1}}", PACKAGE + ".other"),
    (f"topResumedActivity=ActivityRecord{{abc u0 {PACKAGE}/.Main t1}}\n"
     "ResumedActivity: ActivityRecord{abc u0 another.app/.Main t2}", None),
    ("topResumedActivity=null", None), ("Permission Denial", None), ("", None),
    (None, None), pytest.param("x" * 2_000_001, None, id="oversized"),
])
def test_resumed_package_requires_one_unambiguous_current_activity(output, expected):
    assert resumed_package(output) == expected


@pytest.mark.parametrize("raw", ['{}', '[]', '{"foreground": 1}', '{"foreground": true, "cmd": "other"}'])
def test_invalid_parameters_never_query_the_device(raw):
    calls = []
    context = SimpleNamespace(tasker=SimpleNamespace(
        stopping=False, controller=SimpleNamespace(post_shell=lambda *args, **kwargs: calls.append(args))))
    argv = SimpleNamespace(custom_recognition_param=raw, roi=[0, 0, 720, 1280])
    assert DailyLoginAppState().analyze(context, argv) is None and calls == []


@pytest.mark.parametrize("state", ["foreground", "background", "failed", "exception", "cancelled", "stopping"])
def test_probe_uses_only_the_bound_controller_and_checks_completion_and_cancellation(state):
    calls = []
    package = PACKAGE if state != "background" else "com.android.launcher3"
    tasker = SimpleNamespace(stopping=state == "stopping")
    job = SimpleNamespace(succeeded=state != "failed")
    job.wait = lambda: job
    job.get = lambda: f"topResumedActivity=ActivityRecord{{abc u0 {package}/.Main t1}}"

    def shell(command, timeout):
        calls.append((command, timeout))
        if state == "exception":
            raise RuntimeError("read failed")
        if state == "cancelled":
            tasker.stopping = True
        return job

    tasker.controller = SimpleNamespace(post_shell=shell)
    foreground = state != "background"
    argv = SimpleNamespace(custom_recognition_param='{"foreground": ' + str(foreground).lower() + '}',
                           roi=[0, 0, 720, 1280])
    result = DailyLoginAppState().analyze(SimpleNamespace(tasker=tasker), argv)
    assert (result is not None) == (state in ("foreground", "background"))
    assert calls == ([] if state == "stopping" else [(ACTIVITY_COMMAND, 3000)])


def test_registration_failure_is_not_ignored():
    with pytest.raises(RuntimeError, match="register"):
        register_login(SimpleNamespace(register_custom_recognition=lambda *args: False))


@pytest.mark.parametrize("loading", [False, True])
def test_cold_launch_via_title_reaches_home_then_continues_cli_selection(native, pipelines, frame, loading):
    import run_daily

    patch = fast(pipelines)
    if loading:
        patch["NavHome_Normalize"]["timeout"] = 1
        if "DailyLogin_WaitUi" in patch:
            patch["DailyLogin_WaitUi"]["timeout"] = 1000
    patch["DailyMail_Open"].update(action="DoNothing", next=["DailyCore_Done"])
    title = frame("recovery", "title_truck", {
        "title_tap": (248, 1064, 225, 32), "title_logo": (219, 955, 283, 34)})
    native.controller.foreground_package = "com.android.launcher3"
    starts, stops, posted = [], [], []

    def start(package):
        starts.append(package)
        native.controller.foreground_package = PACKAGE
        native.controller.image = title
        if loading:
            frames = iter([np.zeros_like(title)] * 3)
            native.controller.source = lambda: next(frames, native.controller.image.copy())
        return True

    def click(x, y):
        native.controller.image = home_image()
        return True

    def post(entry, overrides):
        posted.append(entry)
        return native.tasker.post_task(entry, patch | overrides)

    native.controller.on_start = start
    native.controller.on_stop = lambda package: stops.append(package) or True
    native.controller.on_click = click
    report = run_daily.execute_tasks(SimpleNamespace(post_task=post), ["login", "mail"], 30, [])
    assert report["result"] == "finished" and len(posted) == 2, report
    assert starts == [PACKAGE] and stops == []
    assert "CommonTitleTap" in report["tasks"][0]["nodes"]
    assert report["tasks"][0]["game_completion"] == "unverified"


@pytest.mark.parametrize("unsafe", ["CommonStopGame", "UnexpectedSpend"])
def test_login_recovery_exception_cannot_hide_a_restart_or_consumption(unsafe):
    import run_daily

    names = ["DailyLogin_Start", "CommonRecoveryRecovered", unsafe, "DailyCore_Done"]
    detail = SimpleNamespace(nodes=[SimpleNamespace(name=name) for name in names])
    job = SimpleNamespace(done=True, succeeded=True, get=lambda: detail)
    calls = []
    tasker = SimpleNamespace(post_task=lambda entry, overrides: calls.append(entry) or job)
    report = run_daily.execute_tasks(tasker, ["login", "friend"], 30, [])
    assert report["result"] == "recovered_unverified" and len(calls) == 1
    assert report["tasks"][1]["result"] == "not_run"
