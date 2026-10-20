import argparse
import os
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath

try:
    import jsonc
except ModuleNotFoundError as error:
    raise ImportError(
        "Missing dependency 'json-with-comments' (imported as 'jsonc').\n"
        f"Install it with:\n  {sys.executable} -m pip install json-with-comments"
    ) from error


ROOT = Path(__file__).resolve().parents[1]
OCR_FILES = ("det.onnx", "rec.onnx", "keys.txt")
PLATFORMS = {
    ("win", "x86_64"): "win-x64",
    ("win", "aarch64"): "win-arm64",
    ("macos", "x86_64"): "osx-x64",
    ("macos", "aarch64"): "osx-arm64",
    ("linux", "x86_64"): "linux-x64",
    ("linux", "aarch64"): "linux-arm64",
}


def _load_json(path):
    with path.open(encoding="utf-8") as stream:
        return jsonc.load(stream)


def _walk_objects(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_objects(child)


def runtime_usage(resource, interface):
    uses_custom = False
    ocr_models = set()
    documents = [interface]
    for path in sorted((resource / "pipeline").rglob("*")):
        if path.is_file() and path.suffix.lower() in (".json", ".jsonc"):
            documents.append(_load_json(path))
    for document in documents:
        for node in _walk_objects(document):
            for key in ("recognition", "action"):
                definition = node.get(key)
                kind = definition.get("type") if isinstance(definition, dict) else definition
                params = definition.get("param", {}) if isinstance(definition, dict) else node
                if kind == "Custom":
                    uses_custom = True
                if key == "recognition" and kind == "OCR":
                    model = params.get("model", "")
                    if not isinstance(model, str) or Path(model).is_absolute() or ".." in Path(model).parts:
                        raise ValueError(f"Invalid OCR model path: {model!r}")
                    ocr_models.add(model)
    return uses_custom, ocr_models


def _agent_configuration(interface):
    agent = interface.get("agent")
    agents = agent if isinstance(agent, list) else [agent]
    if not agents or any(not isinstance(item, dict) or not item.get("child_exec") for item in agents):
        raise ValueError("Custom Pipeline nodes or --with-agent require a declared Agent child_exec")
    return agents


def validate_runtime(runtime_path, *, lock_path):
    # Pure JSON packages do not need to import the Python provisioning module.
    from portable_python import validate_runtime as verify

    return verify(runtime_path, lock_path=lock_path)


def _project_python(executable):
    if not isinstance(executable, str):
        return False
    path = str(PurePosixPath(executable.replace("\\", "/").lower()))
    return path in {"python", "python.exe", "../.runtime/python/python.exe", ".runtime/python/python.exe"}


def _reject_runtime_links(runtime):
    pending = [runtime, runtime.parent]
    while pending:
        path = pending.pop()
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
        if path.is_symlink() or attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise ValueError(f"Portable Python links are not supported: {path}")
        if path != runtime.parent and path.is_dir():
            pending.extend(path.iterdir())


def _ocr_sources(project_root, resource, models):
    sources = {}
    for model in models:
        source = resource / "model" / "ocr" / model
        if all((source / name).is_file() and (source / name).stat().st_size for name in OCR_FILES):
            sources[model] = source
            continue
        # Never replace a partially supplied project model with a different model.
        if model or any((source / name).exists() for name in OCR_FILES):
            raise FileNotFoundError(f"Incomplete OCR model: {source}; require {', '.join(OCR_FILES)}")
        fallback = project_root / "assets" / "MaaCommonAssets" / "OCR" / "ppocr_v5" / "zh_cn"
        if not all((fallback / name).is_file() and (fallback / name).stat().st_size for name in OCR_FILES):
            raise FileNotFoundError(f"Missing OCR model: {source}; prepare {fallback}")
        sources[model] = fallback
    return sources


def install_project(
    project_root, version, os_name, arch, *, output_dir=None, with_agent=False, with_ocr=False
):
    project_root = Path(project_root).resolve()
    output = Path(output_dir).resolve() if output_dir is not None else project_root / "install"
    if output == project_root or any(
        output.is_relative_to(project_root / directory) for directory in ("assets", "agent", "deps", ".runtime")
    ):
        raise ValueError("Output must be a separate staging directory, not project sources or deps")
    for name in (".runtime", "resource", "agent", "interface.json"):
        managed_output = output / name
        if managed_output.is_symlink() or os.path.lexists(managed_output):
            raise ValueError(f"Output already contains managed path {name}; use a new staging output directory")
    platform = PLATFORMS.get((os_name, arch))
    if platform is None and os_name != "android":
        raise ValueError(f"Unsupported OS or architecture: {os_name}/{arch}")
    resource = project_root / "assets" / "resource"
    if not (resource / "pipeline").is_dir():
        raise FileNotFoundError(f"Missing Pipeline directory: {resource / 'pipeline'}")
    interface = _load_json(project_root / "assets" / "interface.json")
    if interface.get("import"):
        raise ValueError("Split interface imports require a project-aware packager; refusing partial packaging")
    # This installer stages the repository's single assets/resource bundle.
    for bundle in interface.get("resource", []):
        paths = bundle.get("path", [])
        paths = [paths] if isinstance(paths, str) else paths
        if any((project_root / "assets" / path).resolve() != resource for path in paths):
            raise ValueError("Only the assets/resource bundle is supported by this installer")
    uses_custom, ocr_models = runtime_usage(resource, interface)
    include_agent = with_agent or uses_custom
    python_runtime = None
    if with_ocr:
        ocr_models.add("")
    if include_agent:
        agents = _agent_configuration(interface)
        for path in (project_root / "agent", project_root / "deps" / "share" / "MaaAgentBinary"):
            if not path.is_dir():
                raise FileNotFoundError(f"Missing Agent component: {path}")
        python_agents = [agent for agent in agents if _project_python(agent["child_exec"])]
        if python_agents:
            if (os_name, arch) != ("win", "x86_64"):
                raise ValueError(f"Unsupported portable Python target: {os_name}/{arch}; require win/x86_64")
            python_runtime = project_root / ".runtime" / "python"
            _reject_runtime_links(python_runtime)
            validate_runtime(python_runtime, lock_path=project_root / "tools" / "python-runtime.lock.json")
            for agent in python_agents:
                agent["child_exec"] = "./.runtime/python/python.exe"
                if agent.get("child_args") == ["../agent/main.py"]:
                    agent["child_args"] = ["./agent/main.py"]
    else:
        interface.pop("agent", None)
    ocr_sources = _ocr_sources(project_root, resource, ocr_models)
    native = project_root / "deps" / "bin"
    library = {"win": "MaaFramework.dll", "macos": "libMaaFramework.dylib"}.get(os_name, "libMaaFramework.so")
    if not (native / library).is_file():
        raise FileNotFoundError(f"Missing MaaFramework runtime: {native / library}")
    for name in ("README.md", "LICENSE"):
        if not (project_root / name).is_file():
            raise FileNotFoundError(f"Missing package file: {project_root / name}")

    native_destination = output if os_name == "android" else output / "runtimes" / platform / "native"
    shutil.copytree(
        native,
        native_destination,
        ignore=shutil.ignore_patterns("*MaaDbgControlUnit*", "*MaaThriftControlUnit*", "*MaaRpc*", "*MaaHttp*", "plugins", "*.node", "*MaaPiCli*"),
        dirs_exist_ok=True,
    )
    if (native / "plugins").is_dir():
        destination = output / "plugins" / platform if platform else output / "plugins"
        shutil.copytree(native / "plugins", destination, dirs_exist_ok=True)
    if include_agent:
        destination = output / "MaaAgentBinary" if os_name == "android" else output / "libs" / "MaaAgentBinary"
        shutil.copytree(project_root / "deps" / "share" / "MaaAgentBinary", destination, dirs_exist_ok=True)
        shutil.copytree(
            project_root / "agent", output / "agent",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"), dirs_exist_ok=True,
        )
        if python_runtime is not None:
            shutil.copytree(
                python_runtime, output / ".runtime" / "python",
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )

    def ignore_unused_ocr(directory, names):
        return {"ocr"} if not ocr_models and Path(directory) == resource / "model" else set()

    shutil.copytree(resource, output / "resource", ignore=ignore_unused_ocr, dirs_exist_ok=True)
    for model, source in ocr_sources.items():
        shutil.copytree(source, output / "resource" / "model" / "ocr" / model, dirs_exist_ok=True)
    interface["version"] = version
    with (output / "interface.json").open("w", encoding="utf-8", newline="\n") as stream:
        jsonc.dump(interface, stream, ensure_ascii=False, indent=4)
        stream.write("\n")
    for name in ("README.md", "LICENSE"):
        shutil.copy2(project_root / name, output)
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description="Stage resources with a prebuilt MaaFramework runtime")
    parser.add_argument("version")
    parser.add_argument("os", choices=("win", "macos", "linux", "android"))
    parser.add_argument("arch", choices=("x86_64", "aarch64"))
    parser.add_argument("--project-root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--with-agent", action="store_true", help="Keep the Agent even without static Custom nodes")
    parser.add_argument("--with-ocr", action="store_true", help="Include default OCR models for dynamic use")
    args = parser.parse_args(argv)
    try:
        output = install_project(
            args.project_root, args.version, args.os, args.arch,
            output_dir=args.output, with_agent=args.with_agent, with_ocr=args.with_ocr,
        )
    except (OSError, ValueError) as error:
        print(f"Packaging failed: {error}", file=sys.stderr)
        return 1
    print(f"Install to {output} successfully. Supply the prebuilt GUI separately.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
