import hashlib
import io
import json
import tarfile

import pytest

from tools.portable_python import ISOLATED_PATHS, extract_python, load_lock, lock_digest, validate_runtime


REFUSAL = (FileNotFoundError, ValueError)


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True), encoding="utf-8")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def prepared(tmp_path):
    root = tmp_path / "project"
    runtime = root / "runtime/python"
    lock_path = root / "tools/python-runtime.lock.json"
    packages = {"MaaFw": "5.14.3", "numpy": "2.2.6", "strenum": "0.4.15", "maaagentbinary": "1.0.0"}
    lock = {
        "schema_version": 1, "target": "win-x64",
        "python": {"version": "3.11.17", "url": "https://example.invalid/python.tar.gz",
                   "sha256": "a" * 64, "archive_root": "python"},
        "packages": {name: {"version": version, "sha256": "b" * 64} for name, version in packages.items()},
    }
    write_json(lock_path, lock)
    files = ["python.exe", "python311.dll", "Lib/os.py"]
    files += [f"Lib/site-packages/{name}/__init__.py" for name in ("maa", "numpy", "strenum", "maaagentbinary")]
    for name in files:
        path = runtime / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"offline marker, not executable")
    (runtime / "python311._pth").write_text(ISOLATED_PATHS, encoding="utf-8")
    manifest = {
        "schema_version": 1, "target": "win-x64", "python_version": "3.11.17",
        "lock_sha256": digest(lock_path), "packages": packages,
        "files": {path.relative_to(runtime).as_posix(): digest(path) for path in runtime.rglob("*") if path.is_file()},
    }
    write_json(runtime / "runtime-manifest.json", manifest)
    return root, runtime, lock_path, manifest


def test_lock_and_valid_runtime_are_data_only(prepared, monkeypatch):
    root, runtime, lock_path, manifest = prepared
    monkeypatch.setenv("PATH", "unchanged")
    assert load_lock(root)["python"]["version"] == "3.11.17"
    assert lock_digest(lock_path) == digest(lock_path)
    assert validate_runtime(runtime, lock_path=lock_path) == manifest
    assert __import__("os").environ["PATH"] == "unchanged"


def test_missing_runtime_is_not_replaced_by_host_python(tmp_path):
    with pytest.raises(REFUSAL):
        validate_runtime(tmp_path / "absent")
    assert not (tmp_path / "absent").exists()


@pytest.mark.parametrize("change", ["hash", "target", "version", "package", "lock", "pth", "manifest"])
def test_runtime_refuses_untrusted_or_incompatible_content(prepared, change):
    _, runtime, lock_path, manifest = prepared
    if change == "hash":
        (runtime / "python.exe").write_bytes(b"tampered")
    elif change == "target":
        manifest["target"] = "win-arm64"
    elif change == "version":
        manifest["python_version"] = "3.12.0"
    elif change == "package":
        manifest["packages"]["MaaFw"] = "0.0.0"
    elif change == "lock":
        lock_path.write_text(lock_path.read_text("utf-8") + "\n", encoding="utf-8")
    elif change == "pth":
        pth = runtime / "python311._pth"
        pth.write_text(".\nC:/untrusted\nimport site\n", encoding="utf-8")
        manifest["files"]["python311._pth"] = digest(pth)
    if change != "manifest":
        write_json(runtime / "runtime-manifest.json", manifest)
    else:
        (runtime / "runtime-manifest.json").unlink()
    with pytest.raises(REFUSAL):
        validate_runtime(runtime, lock_path=lock_path)


@pytest.mark.parametrize("name", ["python.exe", "python311.dll", "python311._pth", "Lib/os.py",
                                  "Lib/site-packages/maa/__init__.py", "Lib/site-packages/numpy/__init__.py"])
def test_required_files_cannot_be_omitted_from_manifest(prepared, name):
    _, runtime, lock_path, manifest = prepared
    (runtime / name).unlink()
    manifest["files"].pop(name)
    write_json(runtime / "runtime-manifest.json", manifest)
    with pytest.raises(REFUSAL):
        validate_runtime(runtime, lock_path=lock_path)


@pytest.mark.parametrize("name", ["../outside.txt", "C:/outside.txt", "Lib\\outside.txt"])
def test_manifest_paths_cannot_escape_runtime(prepared, name):
    _, runtime, lock_path, manifest = prepared
    manifest["files"][name] = "0" * 64
    write_json(runtime / "runtime-manifest.json", manifest)
    with pytest.raises(REFUSAL):
        validate_runtime(runtime, lock_path=lock_path)


def archive(path, name, *, link=False):
    with tarfile.open(path, "w:gz") as tar:
        item = tarfile.TarInfo(name)
        if link:
            item.type, item.linkname = tarfile.SYMTYPE, "../../outside.txt"
            tar.addfile(item)
        else:
            item.size = 5
            tar.addfile(item, io.BytesIO(b"hello"))


def test_safe_archive_is_flattened_under_destination(tmp_path):
    path, destination = tmp_path / "python.tar.gz", tmp_path / "runtime"
    archive(path, "python/Lib/os.py")
    extract_python(path, destination)
    assert (destination / "Lib/os.py").read_bytes() == b"hello"
    assert not (destination / "python").exists()


@pytest.mark.parametrize("name,link", [("python/../../outside.txt", False),
                                     ("python/C:/outside.txt", False),
                                     ("python/Lib\\outside.txt", False),
                                     ("python/Lib/link", True)])
def test_unsafe_archive_never_writes_outside_destination(tmp_path, name, link):
    path, destination = tmp_path / "python.tar.gz", tmp_path / "runtime"
    archive(path, name, link=link)
    with pytest.raises(ValueError):
        extract_python(path, destination)
    assert not (tmp_path / "outside.txt").exists()


@pytest.mark.parametrize("location", ["child", "parent"])
def test_runtime_rejects_windows_junction(prepared, location):
    winapi = pytest.importorskip("_winapi")
    root, runtime, lock_path, _ = prepared
    outside, linked = root / "outside", runtime / "linked"
    outside.mkdir()
    if location == "parent":
        outside, linked = runtime.parent, root / "linked"
    try:
        winapi.CreateJunction(str(outside), str(linked))
    except OSError as error:
        pytest.skip(f"Windows junction creation unavailable: {error}")
    try:
        with pytest.raises(ValueError):
            validate_runtime(runtime if location == "child" else linked / "python", lock_path=lock_path)
    finally:
        linked.rmdir()


@pytest.mark.parametrize("failure", [False, True])
def test_prepare_uses_hash_locked_cache_and_publishes_only_after_pip(prepared, monkeypatch, failure):
    import subprocess
    import tools.prepare_python as module

    root, source, lock_path, _ = prepared
    cached = root / ".runtime/cache/cpython-win-x64.tar.gz"
    cached.parent.mkdir(parents=True)
    with tarfile.open(cached, "w:gz") as tar:
        for path in source.rglob("*"):
            if path.is_file() and path.name != "runtime-manifest.json":
                tar.add(path, arcname="python/" + path.relative_to(source).as_posix())
    lock = json.loads(lock_path.read_text("utf-8"))
    lock["python"]["sha256"] = digest(cached)
    write_json(lock_path, lock)
    calls = []

    def pip(arguments, *, check):
        calls.append(arguments)
        assert check is True
        if failure:
            raise subprocess.CalledProcessError(1, arguments)

    monkeypatch.setattr(module.subprocess, "run", pip)
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *a, **kw: pytest.fail("Valid cache must be offline"))
    if failure:
        with pytest.raises(subprocess.CalledProcessError):
            module.prepare(root)
        assert not (root / ".runtime/python").exists()
    else:
        result = module.prepare(root)
        assert validate_runtime(result, lock_path=lock_path)["lock_sha256"] == digest(lock_path)
    assert len(calls) == 1 and {"--require-hashes", "--isolated", "-E", "-s"} <= set(calls[0])
    assert calls[0][calls[0].index("--platform") + 1] == "win_amd64"
    assert all(item["sha256"] in (cached.parent / "runtime-requirements.txt").read_text("utf-8")
               for item in lock["packages"].values())
