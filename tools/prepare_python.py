"""Prepare the Windows Agent runtime on Windows or a cross-build CI host."""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

from portable_python import (
    ISOLATED_PATHS, extract_python, file_digest, load_lock, lock_digest,
    reject_links, runtime_files, validate_runtime,
)


def prepare(project_root, target="win-x64"):
    root = Path(project_root).resolve()
    lock = load_lock(root)
    if target != lock["target"]:
        raise ValueError(f"Unsupported Python target: {target}")
    runtime = root / ".runtime/python"
    if runtime.exists():
        validate_runtime(runtime, lock_path=root / "tools/python-runtime.lock.json")
        return runtime
    workspace = root / ".runtime"
    workspace.mkdir(exist_ok=True)
    reject_links(workspace)
    cache = workspace / "cache"
    cache.mkdir(exist_ok=True)
    source = lock["python"]
    archive = cache / "cpython-win-x64.tar.gz"
    if not archive.exists() or file_digest(archive) != source["sha256"]:
        if not source["url"].startswith("https://github.com/astral-sh/python-build-standalone/releases/download/"):
            raise ValueError("Python runtime must come from the pinned upstream release")
        partial = cache / f"download-{uuid.uuid4().hex}.part"
        with urllib.request.urlopen(source["url"], timeout=120) as response, partial.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
        if file_digest(partial) != source["sha256"]:
            raise ValueError("Python runtime archive SHA256 mismatch")
        os.replace(partial, archive)
    staging = workspace / f"python-staging-{uuid.uuid4().hex}"
    extract_python(archive, staging, source["archive_root"])
    requirements = cache / "runtime-requirements.txt"
    requirements.write_text("".join(
        f"{name}=={data['version']} --hash=sha256:{data['sha256']}\n"
        for name, data in lock["packages"].items()
    ), encoding="utf-8", newline="\n")
    subprocess.run([
        sys.executable, "-E", "-s", "-m", "pip", "--isolated", "install", "--index-url", "https://pypi.org/simple",
        "--require-hashes", "--only-binary=:all:", "--platform", "win_amd64",
        "--python-version", "3.11", "--implementation", "cp", "--abi", "cp311",
        "--no-compile", "--no-warn-script-location", "--disable-pip-version-check",
        "--target", str(staging / "Lib/site-packages"), "-r", str(requirements),
    ], check=True)
    (staging / "python311._pth").write_text(ISOLATED_PATHS, encoding="utf-8", newline="\n")
    reject_links(staging)
    manifest = {
        "schema_version": 1, "target": target, "python_version": source["version"],
        "lock_sha256": lock_digest(root / "tools/python-runtime.lock.json"),
        "packages": {name: data["version"] for name, data in lock["packages"].items()},
        "files": runtime_files(staging),
    }
    (staging / "runtime-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n",
    )
    validate_runtime(staging, lock_path=root / "tools/python-runtime.lock.json")
    staging.rename(runtime)
    return runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--target", default="win-x64")
    args = parser.parse_args()
    try:
        print(prepare(args.project_root, args.target))
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Portable Python setup failed: {error}\n")


if __name__ == "__main__":
    main()
