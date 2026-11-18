import re
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_launch_capture import (
    LAUNCH_CAPTURE_PIPELINE,
    controller_options,
    ensure_package_installed,
    find_exact_device,
    read_png_size,
)


def test_diagnostic_pipeline_is_private_and_keeps_target_and_png_contract():
    start = LAUNCH_CAPTURE_PIPELINE["TestLaunchAndCapture"]
    assert start["action"] == "StartApp" and start["package"] == "jp.goodsmile.nekoconne"
    assert start["post_delay"] >= 20000
    capture = LAUNCH_CAPTURE_PIPELINE[start["next"][0]]
    assert capture["action"] == "Screencap" and capture["format"] == "png"
    assert capture["filename"] == "nekoconne_launch"


def test_find_exact_device_selects_5557_instead_of_5555():
    devices = [
        SimpleNamespace(address="127.0.0.1:5555"),
        SimpleNamespace(address="127.0.0.1:5557"),
    ]

    assert find_exact_device(devices, "127.0.0.1:5557").address.endswith(":5557")


def test_find_exact_device_never_falls_back():
    devices = [SimpleNamespace(address="127.0.0.1:5555")]

    with pytest.raises(RuntimeError, match="127.0.0.1:5557"):
        find_exact_device(devices, "127.0.0.1:5557")


def test_controller_uses_compatible_lossless_screencap_method(monkeypatch):
    system = {"win32": "Windows", "darwin": "Darwin", "linux": "Linux"}[sys.platform]
    monkeypatch.setattr("platform.system", lambda: system)
    from maa.define import MaaAdbScreencapMethodEnum

    device = SimpleNamespace(
        adb_path="adb.exe",
        address="127.0.0.1:5557",
        input_methods=123,
        config={"key": "value"},
    )

    assert controller_options(device) == {
        "adb_path": "adb.exe",
        "address": "127.0.0.1:5557",
        "screencap_methods": MaaAdbScreencapMethodEnum.EncodeToFileAndPull,
        "input_methods": 123,
        "config": {"key": "value"},
    }


def test_read_png_size(tmp_path):
    png = tmp_path / "screen.png"
    png.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + struct.pack(">I", 13)
        + b"IHDR"
        + struct.pack(">II", 720, 1280)
        + b"\x08\x06\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )

    assert read_png_size(png) == (720, 1280)


def test_read_png_size_rejects_non_png(tmp_path):
    bad = tmp_path / "screen.png"
    bad.write_bytes(b"not a png")

    with pytest.raises(ValueError, match="PNG"):
        read_png_size(bad)


def test_package_check_targets_only_requested_device(monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="package:/data/app/base.apk\n")

    monkeypatch.setattr("run_launch_capture.subprocess.run", fake_run)
    ensure_package_installed(Path("adb.exe"), "127.0.0.1:5557")

    assert calls == [
        [
            "adb.exe",
            "-s",
            "127.0.0.1:5557",
            "shell",
            "pm",
            "path",
            "jp.goodsmile.nekoconne",
        ]
    ]


def test_launch_script_defaults_to_the_project_python():
    script = (ROOT / "scripts/test_nekoconne.ps1").read_text("utf-8")
    assert '[string]$CondaEnv = ""' in script.split("$ErrorActionPreference")[0]
    assert re.search(r'\$Python\s*=\s*Join-Path\s+\$ProjectRoot\s+"\.runtime\\python\\python.exe"', script)


def test_conda_is_only_an_explicit_alternative():
    script = (ROOT / "scripts/test_nekoconne.ps1").read_text("utf-8")
    branch = script.split("if ($CondaEnv) {", 1)[1].split("} else {", 1)[0]
    assert '"run", "-n", $CondaEnv, "python"' in branch
    assert "& conda @CondaArguments" in branch


def test_missing_project_python_stops_with_setup_guidance_without_fallback():
    script = (ROOT / "scripts/test_nekoconne.ps1").read_text("utf-8")
    branch = script.split("} else {", 1)[1]
    assert branch.index("Test-Path") < branch.index("throw") < branch.index("& $Python @Arguments")
    assert "setup_python.ps1" in branch
    assert "catch" not in script
    assert re.search(r"&\s+(?:python|python\.exe)\b", script, re.I) is None
