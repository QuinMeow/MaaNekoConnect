# 项目便携 Python

本项目的 LocalBridge/MFAA Agent 使用项目私有运行时，不依赖全局 Python、Conda、临时测试环境或系统 `PATH`。当前支持 Windows x64；其他目标的 Python Agent 打包明确拒绝，不将 Windows 运行时复制成其他平台的产物。

## 一键准备

在 Windows x64 的仓库根目录运行：

```powershell
.\scripts\setup_python.ps1
```

首次需要访问锁定的 GitHub 发行归档和 PyPI，并使用 Windows 自带的 PowerShell、`tar.exe`。脚本不安装全局 Python，不修改系统或用户 `PATH`，也不创建 Conda 环境。它使用校验过的独立 bootstrap 运行准备工具，最终目录为 `.runtime/python/`；缓存和 staging 也位于已忽略的 `.runtime/` 内。引导进程忽略外部 Python 环境变量和用户 site-packages，退出后清理本次生成的 bootstrap；保留归档缓存时可离线复验现有安装，删掉缓存后重新运行 setup 仍需下载，日常 Agent 启动则不读取该缓存。

若 LocalBridge 正在扫描整个仓库，先将 `.runtime` 加入本地配置的 `file.exclude` 并重启该独立服务，避免监视句柄阻止 staging 目录改名。本机 `config/mpe-localbridge.json` 已完成此设置；此文件不进入 Git。

版本与 SHA256 的唯一配置来源是 [`tools/python-runtime.lock.json`](../../tools/python-runtime.lock.json)。当前 Python 为 Astral Python Build Standalone 的 CPython 3.11.17、20261013 Windows x64 install-only stripped 归档。准备工具对归档和 wheel 使用锁定哈希，pip 使用 `--isolated --require-hashes --only-binary=:all:`，不从未锁定的源码包编译依赖。

应用依赖锁包含四包：

| 包 | 锁定版本 |
| --- | --- |
| MaaFw | 5.14.3 |
| numpy | 2.4.6 |
| MaaAgentBinary | 1.0.1 |
| StrEnum | 0.4.15 |

pytest、jsonschema、referencing、json-with-comments 是开发/构建工具，不属于上述 Agent 应用依赖锁。不要为了执行测试而向已校验的 `.runtime/python` 中安装它们。

## 入口与布局

| 场景 | `child_exec` | `child_args` |
| --- | --- | --- |
| 仓库 `assets/interface.json`，供 LocalBridge/MFAA 加载 | `../.runtime/python/python.exe` | `../agent/main.py` |
| 发布包根目录 `interface.json` | `./.runtime/python/python.exe` | `./agent/main.py` |

源接口的 `..` 相对于 `assets` 布局；发布接口、`agent/`、`.runtime/` 在包内并列。路径不是本机绝对路径，不写入 `%TEMP%`、某个用户目录或系统 Python。运行时的 `python311._pth` 仅使用项目相对路径，不继承外部 `PYTHONPATH` 或全局 site-packages。

[`scripts/test_nekoconne.ps1`](../../scripts/test_nekoconne.ps1) 默认也使用 `.runtime/python/python.exe`。缺失会提示运行 setup 并停止，不自动下载或回退其他 Python。仅当调用者显式提供 `-CondaEnv <已有环境名>` 时，才改用该 Conda 环境；这是旧开发环境的兼容入口，不改变 Agent 配置。

```powershell
# 连接设备并启动游戏，只能在实机任务明确授权后执行。
.\scripts\test_nekoconne.ps1 -Address 127.0.0.1:5557 -AdbPath '<实际 adb.exe 的绝对路径>'
```

## 校验与打包

[`tools/prepare_python.py`](../../tools/prepare_python.py) 在临时 staging 安装后生成 `runtime-manifest.json`，校验成功才发布为 `.runtime/python`。manifest 记录锁文件摘要、目标、版本、应用依赖版本和相对文件哈希。缺失、部分安装、篡改、额外未记录的非缓存文件、非法路径或符号链接/junction 均应拒绝，不自动修补为系统 Python。

[`tools/install.py`](../../tools/install.py) 不负责下载。检测到项目 Python Agent 时，它在写入输出之前调用数据校验器并检查目标平台；失败即停止。输出目录若已有受管路径 `.runtime`、`resource`、`agent` 或 `interface.json`（包括文件、目录或悬空链接），会在任何写入前拒绝，要求另选新的 staging 输出目录；不合并旧运行时/Pipeline，也不删除旧产物。预先复制 GUI 文件的目录仍可使用。成功后复制到 `<输出目录>/.runtime/python`，保留发行许可证和 manifest，过滤 `__pycache__`/`.pyc`，只改发布副本的接口。纯 JSON、无需 Agent 的资源包不附带 Python；显式原生 Agent 保持其配置，不强加 Python。

CI 在 Ubuntu 上使用构建期 Python 3.11 和 pip，为 Windows x64 准备同一锁定运行时，再执行打包。构建宿主 Python 不是最终 Agent 的解释器。MFAAvalonia 固定为 v2.16.2；artifact 上传显式包含隐藏文件，避免 `.runtime` 被遗漏。完整资源、GUI、MaaFramework 原生库与 OCR 模型仍是独立的交付前提，准备 Python 不会替代它们。

MFAAvalonia v2.16.2 的 GUI 仍要求 .NET 10；上游附带 `DependencySetup_依赖库安装_win.bat` 用于其 .NET/VC 依赖。本次打包便携化的是 Python Agent，不代表已将整个 GUI 改造为不需 .NET 的自包含应用。

若准备失败，先停止任务并检查错误、锁文件和 `.runtime` 状态。已有但校验失败的最终运行时不会被静默覆盖；不要直接在运行目录中混装依赖，或为绕过错误把 `child_exec` 改成裸 `python`。

## 开发测试

生产运行时不包含 pytest。开发者可另行准备 bootstrap/venv 或已有 Conda 测试环境，安装 [`requirements.txt`](../../requirements.txt) 和 Schema 依赖，并显式选择它的解释器。测试环境可以与便携 Agent 分开，不应把临时验证路径写回接口或发布包。

本机另已准备持久开发环境 `.runtime/dev/python/python.exe`，供测试与打包使用；它不进入发布包，也不是 Agent 的解释器。

```powershell
$TestPython = '<独立 Python 3.11 测试环境的 python.exe 绝对路径>'
& $TestPython -m pip install -r requirements.txt jsonschema==4.26.0 referencing==0.37.0
& $TestPython -m compileall -q agent tools tests
& $TestPython tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --interface-files assets/interface.json
& $TestPython -m pytest -q
```

离线测试隔离网络、真实进程和设备输入；依赖准备是此前独立、显式的安装步骤。当前便携入口、完整性拒绝和打包行为有离线回归；本说明不将这些结果当作实际 MPE Agent 启动、GUI 发布包搬迁或设备任务的验收。

## 本次验证记录

2026-10-19，本机完成私有运行时安装；在无系统 Python PATH、外部 `PYTHONHOME`/`PYTHONPATH` 无效的环境下，加载 CPython 3.11.17、MaaFw 5.14.3 和项目扩展成功。独立 LocalBridge 2.1.0 使用源接口默认路径的 Agent-only 检查通过，返回 `WaitForFrozenScreen` 和 `FurnitureTimerControl`，在线 MPE 重新连接后显示准备就绪。

最终完整离线测试为 329 项通过，`compileall`、全部资源/接口 Schema、PowerShell 语法、文档本地链接和 `git diff --check` 均通过。测试使用项目内 `.runtime/dev`，不是历史临时环境；Windows 临时目录 ACL 与 junction 用例在允许本机正常文件权限的离线进程中验证。

本机构建含 MFAAvalonia v2.16.2 的完整便携目录，并从带空格的 staging 路径复制到 `install/`，使用发布接口的默认相对路径完成同样的 Agent IPC 检查。未创建控制器或 Tasker，未执行游戏操作或消耗强化券；此记录不代表已在另一台无依赖电脑启动 GUI 或完成游戏任务，也不代表已推送或发布 Release。
