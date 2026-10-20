import argparse
import struct
import subprocess
import time
from pathlib import Path


DEFAULT_ADDRESS = "127.0.0.1:5557"
PACKAGE_NAME = "jp.goodsmile.nekoconne"
LAUNCH_CAPTURE_PIPELINE = {
    "TestLaunchAndCapture": {
        "action": "StartApp", "package": PACKAGE_NAME, "post_delay": 20000,
        "next": ["TestCaptureScreen"],
    },
    "TestCaptureScreen": {
        "action": "Screencap", "filename": "nekoconne_launch", "format": "png",
    },
}
DEFAULT_ADB_PATHS = (
    Path(r"D:\Program Files\Netease\MuMu\nx_main\adb.exe"),
    Path(r"D:\Program Files\Netease\MuMu\nx_device\12.0\shell\adb.exe"),
)


def find_exact_device(devices, address):
    for device in devices:
        if device.address == address:
            return device
    raise RuntimeError(f"未发现目标设备 {address}，不会回退到其他 ADB 设备。")


def controller_options(device):
    from maa.define import MaaAdbScreencapMethodEnum

    return {
        "adb_path": device.adb_path,
        "address": device.address,
        "screencap_methods": MaaAdbScreencapMethodEnum.EncodeToFileAndPull,
        "input_methods": device.input_methods,
        "config": device.config,
    }


def read_png_size(path):
    data = Path(path).read_bytes()[:24]
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"{path} 不是有效的 PNG 文件")
    return struct.unpack(">II", data[16:24])


def resolve_adb_path(value=None):
    if value:
        path = Path(value).expanduser().resolve()
        if path.is_file():
            return path
        raise FileNotFoundError(f"ADB 不存在：{path}")
    for path in DEFAULT_ADB_PATHS:
        if path.is_file():
            return path
    raise FileNotFoundError("未找到 MuMu ADB，请通过 --adb-path 指定。")


def connect_adb(adb_path, address):
    result = subprocess.run(
        [str(adb_path), "connect", address],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0 or "failed" in output.lower():
        raise RuntimeError(f"ADB 连接失败：{output}")


def ensure_package_installed(adb_path, address):
    result = subprocess.run(
        [str(adb_path), "-s", address, "shell", "pm", "path", PACKAGE_NAME],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0 or not result.stdout.strip().startswith("package:"):
        raise RuntimeError(f"目标设备 {address} 未安装 {PACKAGE_NAME}。")


def wait_job(job, description):
    job.wait()
    if not job.succeeded:
        raise RuntimeError(f"{description}失败，状态：{job.status}")


def run(project_root, adb_path, address):
    from maa.controller import AdbController
    from maa.resource import Resource
    from maa.tasker import Tasker
    from maa.toolkit import Toolkit

    project_root = Path(project_root).resolve()
    Toolkit.init_option(str(project_root))
    connect_adb(adb_path, address)
    ensure_package_installed(adb_path, address)

    devices = Toolkit.find_adb_devices(str(adb_path))
    device = find_exact_device(devices, address)
    controller = AdbController(**controller_options(device))
    resource = Resource()
    wait_job(resource.post_bundle(str(project_root / "assets" / "resource")), "资源加载")
    wait_job(controller.post_connection(), "设备连接")

    tasker = Tasker()
    tasker.bind(resource, controller)
    if not tasker.inited:
        raise RuntimeError("Maa Tasker 初始化失败")

    output = project_root / "debug" / "screencap" / "nekoconne_launch.png"
    started_at = time.time()
    wait_job(tasker.post_task("TestLaunchAndCapture", LAUNCH_CAPTURE_PIPELINE), "启动截图任务")

    if not output.is_file() or output.stat().st_mtime < started_at:
        raise RuntimeError(f"未生成新的截图：{output}")
    size = read_png_size(output)
    if size != (720, 1280):
        raise RuntimeError(f"截图尺寸异常：{size[0]}x{size[1]}")
    return output


def main():
    parser = argparse.ArgumentParser(description="启动ネココネ，等待 20 秒并截图")
    parser.add_argument("--project-root", default=Path(__file__).resolve().parents[1])
    parser.add_argument("--adb-path")
    parser.add_argument("--address", default=DEFAULT_ADDRESS)
    args = parser.parse_args()

    output = run(args.project_root, resolve_adb_path(args.adb_path), args.address)
    print(output)


if __name__ == "__main__":
    main()
