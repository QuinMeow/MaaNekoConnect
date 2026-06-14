import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_interface_exposes_only_the_launch_capture_task():
    interface = load_json(ROOT / "assets" / "interface.json")

    assert interface["name"] == "MaaNekoConnect"
    assert interface["github"] == "https://github.com/QuinMeow/MaaNekoConnect"
    assert interface["controller"] == [
        {
            "name": "Android",
            "label": "Android 模拟器",
            "type": "Adb",
            "display_short_side": 720,
        }
    ]
    assert interface["task"] == [
        {
            "name": "框架测试：启动游戏并截图",
            "entry": "TestLaunchAndCapture",
            "controller": ["Android"],
        }
    ]
    assert interface["agent"]["child_args"] == ["../agent/main.py"]


def test_pipeline_starts_game_waits_twenty_seconds_and_captures_png():
    pipeline = load_json(
        ROOT / "assets" / "resource" / "pipeline" / "framework_test.json"
    )

    assert pipeline == {
        "TestLaunchAndCapture": {
            "action": "StartApp",
            "package": "jp.goodsmile.nekoconne",
            "post_delay": 20000,
            "next": ["TestCaptureScreen"],
        },
        "TestCaptureScreen": {
            "action": "Screencap",
            "filename": "nekoconne_launch",
            "format": "png",
        },
    }


def test_template_tasks_and_dangerous_example_click_are_removed():
    tracked_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "agent").glob("*.py")
    )
    assert "post_click(10, 20)" not in tracked_text
    assert not (ROOT / "assets" / "resource" / "pipeline" / "my_task.json").exists()


def test_ci_is_windows_python_only():
    workflow = (ROOT / ".github" / "workflows" / "check.yml").read_text(
        encoding="utf-8"
    )
    assert "runs-on: windows-latest" in workflow
    assert "MaaFw==5.10.5" in (ROOT / "requirements.txt").read_text(encoding="utf-8")
    assert "setup-node" not in workflow
    assert "npm " not in workflow
    assert "compileall" in workflow
    assert "pytest" in workflow


def test_install_workflow_can_read_pull_requests_for_changelog():
    workflow = (ROOT / ".github" / "workflows" / "install.yml").read_text(
        encoding="utf-8"
    )

    assert "permissions:\n  contents: read\n  pull-requests: read" in workflow


def test_installer_rewrites_agent_path_for_packaged_layout():
    installer = (ROOT / "tools" / "install.py").read_text(encoding="utf-8")
    assert 'interface["agent"]["child_args"] = ["./agent/main.py"]' in installer
