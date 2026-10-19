import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OCR_FILES = ("det.onnx", "rec.onnx", "keys.txt")

def write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

def interface(root):
    return json.loads((root / "interface.json").read_text("utf-8"))

def enable_agent(root, executable="python"):
    data = interface(root / "assets")
    data["agent"]["child_exec"] = executable
    write(root / "assets/interface.json", json.dumps(data))
    write(root / "agent/main.py", "# Agent entry\n")
    write(root / "deps/share/MaaAgentBinary/README.md", "binary transport")

@pytest.fixture
def installer(monkeypatch):
    module = importlib.import_module("install")
    module.runtime_checks = []

    def validate(path, *, lock_path):
        module.runtime_checks.append((path, lock_path))
        if not (path / "python.exe").is_file():
            raise FileNotFoundError("Missing portable Python")
        if (path / "runtime-manifest.json").read_text("utf-8") != "verified":
            raise ValueError("Invalid portable Python manifest")
        return {"target": "win-x64"}

    monkeypatch.setattr(module, "validate_runtime", validate, raising=False)
    return module

@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    data = {
        "interface_version": 2, "name": "Test", "version": "0.1.0",
        "resource": [{"name": "Default", "path": ["./resource"]}],
        "agent": {"child_exec": "python", "child_args": ["../agent/main.py"]},
        "task": [{"name": "Test", "entry": "Test"}],
    }
    write(root / "assets/interface.json", json.dumps(data))
    write(root / "assets/resource/pipeline/main.json", '{"Test": {}}')
    write(root / "deps/bin/MaaFramework.dll", "native-5.14.3")
    write(root / "README.md", "Readme")
    write(root / "LICENSE", "License")
    return root


@pytest.fixture
def runtime(project):
    root = project / ".runtime/python"
    for name, content in {"python.exe": "runtime", "runtime-manifest.json": "verified",
                          "LICENSE": "Python license", "__pycache__/stale.pyc": "cache", "stale.pyc": "cache"}.items():
        write(root / name, content)
    return root


def test_pure_json_omits_agent_python_and_ocr_without_mutating_sources(installer, project):
    original = (project / "assets/interface.json").read_bytes()
    output = project.parent / "desktop"
    write(output / "MFAAvalonia.exe", "existing GUI")
    assert installer.main(["vtest", "win", "x86_64", "--project-root", str(project), "--output", str(output)]) == 0
    assert "agent" not in interface(output) and interface(output)["version"] == "vtest"
    assert not any((output / name).exists() for name in ("agent", ".runtime", "libs/MaaAgentBinary"))
    assert not (output / "resource/model/ocr").exists()
    assert (output / "resource/pipeline/main.json").is_file()
    assert (output / "runtimes/win-x64/native/MaaFramework.dll").is_file()
    assert (project / "assets/interface.json").read_bytes() == original
    assert installer.runtime_checks == []
    assert (output / "MFAAvalonia.exe").read_text("utf-8") == "existing GUI"


@pytest.mark.parametrize("executable", ["python", "python.exe", "../.runtime/python/python.exe",
                                        "./.runtime/python/python.exe", r"..\.runtime\python\python.exe"])
def test_python_agent_is_verified_portable_and_relocatable(installer, project, runtime, executable):
    enable_agent(project, executable)
    write(project / "assets/resource/pipeline/main.json", '{"Test":{"action":"Custom"}}')
    original = (project / "assets/interface.json").read_bytes()
    output = installer.install_project(project, "vtest", "win", "x86_64")
    assert interface(output)["agent"] == {
        "child_exec": "./.runtime/python/python.exe", "child_args": ["./agent/main.py"]
    }
    assert installer.runtime_checks == [(runtime, project / "tools/python-runtime.lock.json")]
    for name in ("python.exe", "LICENSE", "runtime-manifest.json"):
        assert (output / ".runtime/python" / name).read_bytes() == (runtime / name).read_bytes()
    assert not any((output / ".runtime/python" / name).exists() for name in ("__pycache__", "stale.pyc"))
    assert (output / "agent/main.py").is_file() and (output / "libs/MaaAgentBinary/README.md").is_file()
    assert (project / "assets/interface.json").read_bytes() == original
    assert str(project) not in (output / "interface.json").read_text("utf-8")


@pytest.mark.parametrize("damage", ["missing", "partial", "corrupt", "old_directory", "old_file", "dangling", "old_resource", "old_agent", "old_interface"])
def test_invalid_or_existing_runtime_fails_without_output_writes(installer, project, runtime, monkeypatch, damage):
    enable_agent(project)
    output = project / "install"
    relative = {"old_directory": ".runtime/old.txt", "old_resource": "resource/pipeline/old.json",
                "old_agent": "agent/old.py", "old_interface": "interface.json"}.get(damage, ".runtime")
    marker = output / relative
    if damage.startswith("old_"):
        write(marker, "preserve old staging")
    elif damage == "dangling":
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == marker)
    elif damage == "missing":
        (runtime / "python.exe").unlink()
    elif damage == "partial":
        (runtime / "runtime-manifest.json").unlink()
    else:
        write(runtime / "runtime-manifest.json", "corrupt")
    occupied = damage.startswith("old_") or damage == "dangling"
    with pytest.raises(ValueError if occupied else (FileNotFoundError, ValueError), match="staging" if occupied else None):
        installer.install_project(project, "vtest", "win", "x86_64", with_agent=True)
    if damage.startswith("old_"):
        assert set(output.iterdir()) == {output / relative.split("/")[0]}
        assert marker.read_text("utf-8") == "preserve old staging"
    else:
        assert not output.exists()

@pytest.mark.parametrize("os_name,arch", [("win", "aarch64"), ("linux", "x86_64"), ("android", "aarch64")])
def test_python_agent_rejects_unsupported_targets_before_staging(installer, project, runtime, os_name, arch):
    enable_agent(project)
    with pytest.raises(ValueError, match="[Uu]nsupported.*Python|Python.*[Uu]nsupported"):
        installer.install_project(project, "vtest", os_name, arch, with_agent=True)
    assert not (project / "install").exists() and installer.runtime_checks == []

def test_explicit_native_agent_does_not_require_python(installer, project):
    enable_agent(project, "./agent/native.exe")
    output = installer.install_project(project, "vtest", "win", "x86_64", with_agent=True)
    assert interface(output)["agent"] == interface(project / "assets")["agent"]
    assert installer.runtime_checks == [] and not (output / ".runtime").exists()

@pytest.mark.parametrize("target", ["parent", ".", "linked"])
def test_python_directory_links_are_not_followed(installer, project, runtime, monkeypatch, target):
    enable_agent(project)
    write(runtime / "linked", "link target")
    link = runtime.parent if target == "parent" else runtime / target
    original = Path.iterdir
    def entries(path):
        if target == "parent" and path == runtime:
            pytest.fail("Link followed")
        return original(path)
    monkeypatch.setattr(Path, "iterdir", entries)
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link)
    with pytest.raises(ValueError, match="[Ll]ink"):
        installer.install_project(project, "vtest", "win", "x86_64", with_agent=True)
    assert not (project / "install").exists()

@pytest.mark.parametrize("node,custom,models", [
    ({"recognition": {"type": "Custom", "param": {}}}, True, set()),
    ({"recognition": "And", "all_of": [{"action": "Custom"}]}, True, set()),
    ({"recognition": {"type": "OCR", "param": {"model": "jp"}}}, False, {"jp"}),
    ({"recognition": "Or", "any_of": [{"recognition": "OCR"}]}, False, {""}),
])
def test_nested_runtime_requirements_are_detected(installer, project, node, custom, models):
    write(project / "assets/resource/pipeline/main.json", json.dumps({"Test": node}))
    assert installer.runtime_usage(project / "assets/resource", {}) == (custom, models)


@pytest.mark.parametrize("missing", ["declaration", "sources"])
def test_jsonc_custom_requires_declared_agent_components(installer, project, missing):
    write(project / "assets/resource/pipeline/extra.jsonc", '// extension\n{"Extra":{"action":"Custom"}}')
    if missing == "declaration":
        data = interface(project / "assets")
        data.pop("agent")
        write(project / "assets/interface.json", json.dumps(data))
    with pytest.raises((FileNotFoundError, ValueError), match="[Aa]gent"):
        installer.install_project(project, "vtest", "win", "x86_64")
    assert not (project / "install").exists()


@pytest.mark.parametrize("model,source", [("", "fallback"), ("", "project"), ("jp", "project"), ("", None)])
def test_used_ocr_models_are_required_and_not_overwritten(installer, project, model, source):
    write(project / "assets/resource/pipeline/main.json", json.dumps({"Test": {"recognition": "OCR", "model": model}}))
    target = project / "assets/resource/model/ocr" / model
    if source:
        for name in OCR_FILES:
            write(project / "assets/MaaCommonAssets/OCR/ppocr_v5/zh_cn" / name, "fallback")
            if source == "project":
                write(target / name, "project")
        output = installer.install_project(project, "vtest", "win", "x86_64")
        assert (output / "resource/model/ocr" / model / "rec.onnx").read_text() == source
    else:
        with pytest.raises(FileNotFoundError, match="OCR"):
            installer.install_project(project, "vtest", "win", "x86_64")
        assert not (project / "install").exists()


def test_workflow_prepares_locked_runtime_before_install():
    workflow = (ROOT / ".github/workflows/install.yml").read_text("utf-8")
    assert "include-hidden-files: true" in workflow
    assert 'MFAA_VERSION: "v2.16.2"' in workflow
    assert "actions/setup-python@v5" in workflow and 'python-version: "3.11"' in workflow
    assert workflow.index("prepare_python.py --project-root .. --target win-x64") < workflow.index("python ./install.py")
