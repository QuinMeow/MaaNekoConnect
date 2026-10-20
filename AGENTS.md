# MaaNekoConnect 工作指南

## 先读与导航

- 先读 [项目理解与计划对照](docs/zh_cn/project_understanding.md)，区分当前实现、上游计划和历史验证。
- `assets/interface.json`：控制器、资源、Agent 入口和对外任务；`assets/resource/pipeline/`：游戏流程。`navigation.json` 是公共导航，`furniture_enhance.json` 是单轮强化，`furniture_filter.json` 是筛选，`soleil_shop.json` 是店铺依頼，`furniture_schedule.json` / `furniture_timer.json` 是调度与计时；`common_recovery.json` 为共用异常恢复与有界重启。
- `tools/run_launch_capture.py`、`scripts/test_nekoconne.ps1`：设备连接与启动截图验证。
- `agent/main.py`：AgentServer 入口；`agent/extensions.py`：注册必要扩展；`agent/recovery.py`：原生静止检测的布尔识别桥及全黑帧退化边界处理；`agent/furniture_timer.py`：原生 OCR 时间解析、Context 局部计时与可取消等待。
- `tests/`：离线回归测试；`.github/workflows/check.yml`：开发验证依据。
- `tools/configure.py`、`tools/install.py`、`.github/workflows/install.yml`：OCR 配置、打包和发布；不是日常测试入口。
- `scripts/setup_python.ps1`、`tools/python-runtime.lock.json`：Windows x64 项目便携 Python；布局、准备和验证边界见 [便携 Python 说明](docs/zh_cn/portable_python.md)。

## 工作约定

- 开始先运行 `git rev-parse --show-toplevel`、`git status --short --branch`，阅读已有修改；保留用户工作，不擅自重置、切分支、提交或推送。
- 当前目录就是实现仓库根目录，命令直接从这里运行。上游计划仓库独立存在，不假设本机有外层目录或其脚本。
- 优先 JSON Pipeline 和 MaaFramework 现有 API；只有 JSON 无法清晰表达时才加入小型、可测试的 Python 扩展，不重复实现框架能力。
- 节点按职责使用 `NavHome_*` / `NavSoleil_*`、`FurnitureEnhance_*`、`FurnitureFilter_*`、`Soleil_*`、`FurnitureSchedule_*` / `FurnitureTimer_*`。Soleil 指咖啡店，强化是独立业务；公共导航不得夹带消费。复用识别时注意 And/Or 不继承 action/next/inverse，锚点不是调用栈；接口配置参数，调度由 Pipeline/必要扩展执行。
- 强化单轮至多 5 次尝试，轮末有新增确认才依頼一次。只有正常新轮初始化轮内许可；恢复不得清零轮内、全程消费、调度或恢复预算。动态最短/最长仅指可见前五格忙碌家具，读取不完整时明确回退固定间隔，不声称全局队列。
- 默认目标为 `127.0.0.1:5557`，不得自动回退到 `5555` 或其他设备。测试隔离真实 ADB、网络和 Conda；实机操作须在任务授权范围内进行。
- Agent 默认使用项目私有 `.runtime/python`，不依赖全局 Python、Conda、临时验证目录或系统 `PATH`。Windows x64 用 `scripts/setup_python.ps1` 准备锁定的 Python 3.11.17 与四个应用依赖；源接口为 `../.runtime/python/python.exe`，发布接口为 `./.runtime/python/python.exe`。缺失/损坏失败即停，不自动回退或向生产运行时安装 pytest；开发测试使用独立环境。
- 异常恢复复用 `common_recovery.json`，在同一次 Task 中回到安全入口重新识别，不重放未确认的消费动作，也不清零消费或恢复许可计数。静止检测须检查返回值并在重启前重新判页；正常静态空闲不能等同于卡死。规则与验证边界见 [通用恢复说明](docs/zh_cn/develop/common_recovery.md)。
- 游戏事实附来源、版本或观测日期，推断单列。历史截图成功不代表当前机器、账号和游戏版本已验证。
- 功能修复先补能复现问题的失败测试，再实现和回归；纯文档变更核对事实与链接即可。保持 UTF-8、LF，按需更新接口、Pipeline、测试与说明。
- 测试保持轻量：每个功能或模块最多一个 `test_*.py`，每文件不超过 200 个物理行（含导入、辅助代码、注释和空行）；可以有多个用例和参数化边界测试。不按结构、流程、视觉重复拆分同一模块，不压行或转移到辅助文件规避限制。
- 优先验证行为与稳定的安全契约（设备精确选择、防误消费/重放、有界恢复、可取消等待），不逐字段复述 Pipeline 或锁死无关节点名、文案和完整分支列表；精确顺序确为安全要求时例外。结构合法性交给 Schema 和统一引用检查。`conftest.py` 只放真正共用的加载、离线隔离与测试引擎配置，同样不超过 200 行。
- 当前用户要求及实际代码优先于上游旧指令。本地保留此 `AGENTS.md`；不照搬上游的外层记忆治理、自动提交或双仓库目录要求。

## MPE 编辑与桌面交付

- 默认开发方式为独立 LocalBridge 后台服务 + [在线 MPE](https://mpe.codax.site/stable/)。MPE Desktop 是同一编辑器的另一种入口，不要求同时启动，不默认另装 Desktop、AI 助手或 MCP；已安装的软件不擅自卸载。
- MPE 是开发编辑器，LocalBridge 负责本地文件与调试通信，MaaFramework 是任务执行引擎；最终用户桌面程序继续采用 MFAAvalonia，不把 MPE Desktop 当作 MaaNekoConnect 用户客户端。
- 任务源以 `assets/interface.json`、`assets/resource/pipeline/` 和 `assets/resource/image/` 为准。临时导出、下载和本机配置统一放在已忽略的 `config/`，不要把该目录中的副本当作运行资源或用下载文件无意覆盖源文件。
- 优先直接修改仓库 JSON，再通过 LocalBridge 文件变更通知在在线 MPE 中重载查看；自动重载默认不保证开启。通过图形编辑器修改时，确认画布已关联真实本地路径并显式保存，浏览器缓存、剪贴板导入和临时标签不等于磁盘文件。磁盘与未保存画布冲突时先确认，不覆盖用户编辑。
- 修改 JSON 流程和识别图片通常无需重新编译桌面程序，但要停止任务、保存并重载资源后再运行；不承诺运行中热更新。仓库资源与发布包内资源是两份副本，修改仓库不会自动同步给已安装的客户端，交付仍需资源同步或重新打包。
- LocalBridge 仅监听本机回环地址，浏览器来源按需限制；不为连接方便暴露到局域网或公网。连接服务、编辑文件或做只读接口检查，不等于获准连接其他设备、运行游戏任务或消耗强化券。
- 先用 `service status --json` 查询已有实例、项目根目录和实际 `address/state/managed`，再决定连接或启动；不要重复启动、猜端口，或擅自停止其他实例和任务。常用端口为 `9066`，不是必须固定的服务状态。
- 本机已验证的完整 LocalBridge 位于 `%LOCALAPPDATA%\mpelb\mpelb.exe`，可脱离 Desktop 独立运行；旧的 `deps/mpe-localbridge/mpelb.exe` 不代表附带完整 MaaFramework 依赖。路径、本机 `config/mpe-localbridge.json` 和依赖状态必须先检查，不假定新 checkout 已准备好。

查询和独立启动示例（先查状态，只有确认没有现有实例时才启动；后台辅助进程使用隐藏窗口）：

```powershell
$lb = Join-Path $env:LOCALAPPDATA 'mpelb\mpelb.exe'
& $lb service status --json
& $lb --config .\config\mpe-localbridge.json --root . --interface .\assets\interface.json --port 9066
```

### 直接接口边界

- 2026-10-19 核验的 MPE/LocalBridge v2.1.0 提供自定义 WebSocket `{path, data}` 协议，不是 REST 或原生 MCP 服务；内置 Harness 是编辑器里的 AI 助手，也不是外部 MCP。不要将 `ws://127.0.0.1:9066` 作为 MCP 地址，不重复实现或安装没有必要的适配层。
- 直接调用前确认当前版本与官方协议，完成 `/system/handshake` 并等待成功响应；不猜 `protocol_version`，也不假定协议版本必然等于产品版本，该版本握手不匹配会导致服务退出。按响应路由过滤交错通知，不假定每次接收都是当前请求的回复。
- 只读文件用 `/etl/open_file`，响应 `/lte/file_content`；优先使用 `/lte/file_list` 返回的原样 `file_path`，保留分隔符、大小写及前缀，通过 JSON 序列化器转义，不自行改成正斜杠或 `file://`。本机实测原生反斜杠路径成功，改写的正斜杠路径会返回 `FILE_NOT_FOUND`；这不是对模板或配置中路径格式的全局限制。该接口读取磁盘解析后的 JSON，不含未保存画布，也不保证保留 JSONC 注释与原始格式。
- `/etl/open_external` 会启动外部程序，不是只读文件接口。随机 HTTP 管理端口只用于服务管理，不是任务 REST/MCP；管理发现文件含秘密 token，不打印或传播。优先使用 CLI 查询状态，不为探测调用停止或强制结束接口。
- 协议细节以固定版本的 [LocalBridge 说明](https://github.com/kqcoxn/MaaPipelineEditor/blob/v2.1.0/LocalBridge/README.md#websocket-api) 和实际安装版本源码为准；升级后重新核验，历史连接成功不代表当前服务在线。

## 开发与验证命令

以下均从仓库根目录执行。生产 Agent 基准为便携 Python 3.11.17、`MaaFw==5.14.3`；首次准备使用 `scripts/setup_python.ps1`，不改全局 Python 或 `PATH`。生产应用依赖锁不含 pytest，以下检查必须显式选择另行准备的 Python 3.11 开发测试环境。缺依赖时报告阻塞，安装依赖按当前任务授权执行。

```powershell
$env:PYTHONUTF8 = "1"
$TestPython = '<独立测试环境的 python.exe 绝对路径>'
& $TestPython -m compileall -q agent tools tests
& $TestPython tools/validate_schema.py --schema-dir deps/tools --resource-dirs assets/resource --interface-files assets/interface.json
& $TestPython -m pytest -q
git diff --check
git status --short --untracked-files=all
```

Schema 校验还需要 `jsonschema`、`referencing`；CI 固定为 `4.26.0`、`0.37.0`。`tools/validate_schema.py` 的默认 schema 目录不适用本 checkout，须保留上面的 `--schema-dir deps/tools`。
若已有 `maanekoconnect` 测试环境，可显式使用 `conda run -n maanekoconnect python ...`；不要假定此环境存在，也不要因此改写 Agent 入口。`package.json` 没有 npm scripts，不使用虚构的 `npm test` 或 `npm run build`。

仅在任务明确包含实机验证且目标设备、ADB、依赖已准备好时运行：

```powershell
.\scripts\test_nekoconne.ps1 -Address 127.0.0.1:5557 -AdbPath '<实际 adb.exe 的绝对路径>'
```

该脚本默认使用项目私有 Python，缺失时提示运行 setup 并停止；仅显式 `-CondaEnv <环境名>` 才使用兼容 Conda 路径，不自动回退。命令会连接设备并启动游戏，输出 `debug/screencap/nekoconne_launch.png`。检查任务结果、截图是否为本次生成及内容是否正确；720×1280 PNG 检查本身不能证明到达首页。

## 完成前

检查完整改动（含未跟踪文件）、相对链接和 `git diff --check`，确认只改了授权范围。行为变更运行相关测试及上述离线验证；缺少环境时报告未执行项目和原因，不把历史 CI 当成本次结果。交付写清文件、行为或文档变化、验证证据与阻塞；提交、推送、发布按用户当前授权执行。
