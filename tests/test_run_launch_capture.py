import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from run_launch_capture import ensure_package_installed, find_exact_device, read_png_size


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
