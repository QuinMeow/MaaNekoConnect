# MaaNekoConnect 工作指南

## 先读与导航

- 先读 [项目理解与计划对照](docs/zh_cn/project_understanding.md)，区分当前实现、上游计划和历史验证。
- `assets/interface.json`：控制器、资源、Agent 入口和对外任务；`assets/resource/pipeline/`：游戏流程。
- `tools/run_launch_capture.py`、`scripts/test_nekoconne.ps1`：设备连接与启动截图验证。
- `agent/main.py`：AgentServer 入口；`agent/extensions.py`：必要的自定义扩展，当前为空壳。
- `tests/`：离线回归测试；`.github/workflows/check.yml`：开发验证依据。
- `tools/configure.py`、`tools/install.py`、`.github/workflows/install.yml`：OCR 配置、打包和发布；不是日常测试入口。

## 工作约定

- 开始先运行 `git rev-parse --show-toplevel`、`git status --short --branch`，阅读已有修改；保留用户工作，不擅自重置、切分支、提交或推送。
- 当前目录就是实现仓库根目录，命令直接从这里运行。上游计划仓库独立存在，不假设本机有外层目录或其脚本。
- 优先 JSON Pipeline 和 MaaFramework 现有 API；只有 JSON 无法清晰表达时才加入小型、可测试的 Python 扩展，不重复实现框架能力。
- 默认目标为 `127.0.0.1:5557`，不得自动回退到 `5555` 或其他设备。测试隔离真实 ADB、网络和 Conda；实机操作须在任务授权范围内进行。
- 游戏事实附来源、版本或观测日期，推断单列。历史截图成功不代表当前机器、账号和游戏版本已验证。
- 功能修复先补能复现问题的失败测试，再实现和回归；纯文档变更核对事实与链接即可。保持 UTF-8、LF，按需更新接口、Pipeline、测试与说明。
- 当前用户要求及实际代码优先于上游旧指令。本地保留此 `AGENTS.md`；不照搬上游的外层记忆治理、自动提交或双仓库目录要求。

## 开发与验证命令

以下均从仓库根目录执行。基准为 Python 3.11、`MaaFw==5.14.3`；环境必须已配置。缺依赖时报告阻塞，安装依赖按当前任务授权执行。

```powershell
$env:PYTHONUTF8 = "1"
python -m compileall -q agent tools tests
python tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --interface-files assets/interface.json
python -m pytest -q
git diff --check
git status --short --untracked-files=all
```

Schema 校验还需要 `jsonschema`、`referencing`；CI 固定为 `4.26.0`、`0.37.0`。`tools/validate_schema.py` 的默认 schema 目录不适用本 checkout，须保留上面的 `--schema-dir deps/tools`。
若已有 `maanekoconnect` 环境，可给 Python 命令加 `conda run -n maanekoconnect` 前缀；不要假定此环境一定存在。`package.json` 没有 npm scripts，不使用虚构的 `npm test` 或 `npm run build`。

仅在任务明确包含实机验证且目标设备、ADB、依赖已准备好时运行：

```powershell
.\scripts\test_nekoconne.ps1 -CondaEnv maanekoconnect -Address 127.0.0.1:5557 -AdbPath '<实际 adb.exe 的绝对路径>'
```

该命令会连接设备并启动游戏，输出 `debug/screencap/nekoconne_launch.png`。检查任务结果、截图是否为本次生成及内容是否正确；720×1280 PNG 检查本身不能证明到达首页。

## 完成前

检查完整改动（含未跟踪文件）、相对链接和 `git diff --check`，确认只改了授权范围。行为变更运行相关测试及上述离线验证；缺少环境时报告未执行项目和原因，不把历史 CI 当成本次结果。交付写清文件、行为或文档变化、验证证据与阻塞；提交、推送、发布按用户当前授权执行。
