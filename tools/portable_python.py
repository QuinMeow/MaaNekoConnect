"""Validate and unpack the project-owned, hash-locked Windows Python runtime."""

import hashlib
import json
import re
import shutil
import tarfile
from pathlib import Path, PurePosixPath


LOCK_PATH = Path(__file__).with_name("python-runtime.lock.json")
ISOLATED_PATHS = ".\nDLLs\nLib\nLib/site-packages\n../../agent\n../../tools\nimport site\n"
REQUIRED_FILES = (
    "python.exe", "python311.dll", "python311._pth", "Lib/os.py",
    "Lib/site-packages/maa/__init__.py", "Lib/site-packages/numpy/__init__.py",
)


def file_digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def lock_digest(path):
    return file_digest(path)


def load_lock(project_root):
    path = Path(project_root) / "tools/python-runtime.lock.json"
    lock = json.loads(path.read_text("utf-8"))
    if lock.get("schema_version") != 1 or lock.get("target") != "win-x64":
        raise ValueError("Unsupported Python runtime lock")
    for item in [lock["python"], *lock["packages"].values()]:
        if not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("Runtime downloads require a pinned SHA256")
    return lock


def _safe_relative(name):
    path = PurePosixPath(name)
    if not name or "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Unsafe runtime path: {name}")
    return path


def reject_links(root):
    root = Path(root)
    def check(path):
        # Junction support must also work on Python 3.11.
        junction = getattr(path, "is_junction", lambda: False)()
        reparse = path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & 0x400
        if path.is_symlink() or junction or reparse:
            raise ValueError(f"Linked/reparse runtime path is not supported: {path}")

    for path in reversed((root, *root.parents)):
        check(path)
    for path in root.rglob("*"):
        check(path)


def extract_python(archive_path, destination, archive_root="python"):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    reject_links(destination)
    with tarfile.open(archive_path, "r:gz") as archive:
        for item in archive:
            relative = _safe_relative(item.name)
            if not relative.parts or relative.parts[0] != archive_root:
                raise ValueError(f"Unexpected Python archive member: {item.name}")
            if not item.isfile() and not item.isdir():
                raise ValueError(f"Unsupported Python archive member: {item.name}")
            target = destination.joinpath(*relative.parts[1:])
            if not target.resolve().is_relative_to(destination.resolve()):
                raise ValueError(f"Archive member escapes runtime: {item.name}")
            if item.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)


def runtime_files(root):
    return {
        path.relative_to(root).as_posix(): file_digest(path)
        for path in sorted(Path(root).rglob("*"))
        if path.is_file() and path.name != "runtime-manifest.json"
        and path.suffix != ".pyc" and "__pycache__" not in path.parts
    }


def validate_runtime(runtime_path, *, lock_path=None):
    root = Path(runtime_path)
    lock_path = Path(lock_path) if lock_path else LOCK_PATH
    if not root.is_dir():
        raise FileNotFoundError(f"Missing portable Python: {root}; run scripts/setup_python.ps1")
    reject_links(root)
    lock = load_lock(lock_path.parent.parent)
    manifest = json.loads((root / "runtime-manifest.json").read_text("utf-8"))
    expected = {
        "schema_version": 1, "target": lock["target"],
        "python_version": lock["python"]["version"], "lock_sha256": lock_digest(lock_path),
        "packages": {name: data["version"] for name, data in lock["packages"].items()},
    }
    if any(manifest.get(name) != value for name, value in expected.items()):
        raise ValueError("Portable Python manifest does not match the runtime lock")
    hashes = manifest.get("files")
    if not isinstance(hashes, dict) or not all(name in hashes for name in REQUIRED_FILES):
        raise ValueError("Incomplete portable Python manifest")
    for name in hashes:
        _safe_relative(name)
    if runtime_files(root) != hashes:
        raise ValueError("Portable Python files are missing, changed, or unrecorded")
    if (root / "python311._pth").read_text("utf-8") != ISOLATED_PATHS:
        raise ValueError("Portable Python must use project-relative isolated paths")
    return manifest
