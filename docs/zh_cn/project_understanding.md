# MaaNekoConnect 项目理解与计划对照

## 主要结论

项目目标是基于 MaaFramework 自动化ネココネ（包名 `jp.goodsmile.nekoconne`）。本次初始核对的实现是框架连通性基线：精确选择 ADB 设备，启动游戏，等待 20 秒，再保存截图。后续于 2026-10-19 新增实验性[家具单轮补位及间隔调度](develop/soleil_upgrade.md)、[公共首页/Soleil 导航](develop/navigation.md)和[通用异常恢复](develop/common_recovery.md)。导航、筛选、单轮强化、店铺依頼、调度与计时分模块使用 JSON；`agent/recovery.py` 是原生冻结识别桥，`agent/furniture_timer.py` 只处理 OCR 时间数据和等待。默认单轮最多 5 次尝试、轮末一次依頼，可配置固定/最短/最长剩余时间及总轮数，动态时间只覆盖可见忙碌格。下文架构、单一任务和差距表保留初次核对快照，不代表新增功能后的完整清单；验证边界以对应说明为准。尚不能把项目理解成可用的完整日常助手。

上游 `MaaNekoConnect_Codex` 的主要内容是双仓库协作、环境准备、研究记录和 Agent 长期记忆治理；其任务清单只明确完成框架基线并要求继续研究实际游戏流程，没有给出具体玩法功能的优先级列表。本文提出的后续顺序属于基于差距的建议，需与用户确定业务目标。

2026-10-19 北京时间 23 点后的[跨日观测](develop/daily_observation_20261019.md)新增日期变化恢复，以及有共享次数上限的通用登录提示清理。用户停止手机操作并重新授权后，继续至 10 月 20 日 00:50 的[每日任务人工探索](develop/daily_tasks_research.md)：九项独立条件加汇总，验证收入、问候、旧配送领取、VR 免费跳过及一次免费比赛，最终 80 DayPt、8/9，仅交换未做。另采集访问拒绝和游玩设备确认并加入公共异常恢复，有限确认耗尽即停止，不穿透底层 Close。该人工探索阶段尚未自动执行每日任务；新增自动恢复路径以离线测试为证据，不把手动观察算成自动全链验收。

2026-10-20 随后开始[每日自动化实验](develop/daily_automation.md)：旧组合入口通过独立 OCR 按每日未完成条件调度，自动实测一次随机交换所 1000 金币兑换及后续领奖，账号到 9/9、100P，再次运行未重复消费。该结果承接上文人工/手机已完成的八项，不是全新游戏日九项全自动验收；旧版关闭新配送/礼物、广告仅定位的配置也只是这一历史阶段。

本轮按用户新要求改为任务列表内可选择、排序的 12 个独立每日模块：九项每日条件对应的玩法/登录，加邮箱、社团和领奖，领奖最后；已选玩法不再因每日已 1/1 或 9/9 而屏蔽。CLI 使用显式 `--tasks` 顺序列表，同一入口只执行一次，失败停止后续项，模块回首页只报告执行结束而非游戏条件完成。`DailyLogin_Start` / CLI `login` 位于界面日常列表首项，只经 `NavHome_Ensure` 到首页、清理登录奖励与公告，不执行玩法或每日列表领奖；其他模块仍自行导航，不强制依赖先运行登录。当前架构为 `daily_core.json` 共享导航与收尾、独立 `daily_*.json` 业务流程，加小型必要扩展：[`agent/delivery.py`](../../agent/delivery.py) 聚合原生地图识别、在 Context 中保存选中 pin 并确认派出，广告关闭扩展仅提供有界关闭和默认不外发的可选视觉 provider，不替代 JSON 调度。配送最多 36 单、每单仅允许已知的 `1000/2500/5000/10000` 电池成本，订单计数与 pin 数一致且全部启动后才允许一次每日免费更新；没有钻石更新或立即完成路径。好友改为一键问候；VR 目标为用尽当前免费次数，但每次精确读取 `N` 后，领奖后必须恰好为 `N-1` 才能继续，计数不变、跳变、增加或缺失均停止、不重放；礼物使用最高已通关关卡快速开店，邮件容量不足和工会可选捐款各自有界。细节与实现边界见[每日自动化说明](develop/daily_automation.md)。

新模块本轮实机只补充了配送六旧单批量领取、一次免费更新和一份 `1000` 电池新单倒计时确认，以及礼物一次人工快速开店胜利，不能据此声称独立入口全链已验收。首次自动批次 `friend vr gift rewards` 被新的「登录失败，结束游戏」提示阻断：报告 `stopped`、消费尝试为空，后三项 `not_run`；不是好友模板失效。通用 Close 当时误关闭该提示，有界重启后停在启动器，后续多次启动仍未进入游戏、未取得 crashlog，现已停止实机。新增该提示优先判定、一次确认和沿用原重启预算的修复以离线回归为证据，尚未实机验收；不反复启动、不重放业务，也不将旧总入口的成功当作新模块验证。

2026-10-20 用户实测单任务后，继续进行[串行衔接调试](develop/daily_automation.md#串行衔接修复与-mpe-验证)。各入口和 `daily_core.json` 收尾适配统一调用 `navigation.json` 的纯 `NavHome_Normalize`，从已知业务页/弹窗回首页再交还本次调用方，不继承前 Task 业务锚点；正常静态业务页不因卡在旧入口而重启。实机发现并修正社团标题被爪印裁切干扰的 OCR ROI。MPE 正反序各五项均最终到首页，十二日常入口及家具衔接有原生离线模拟；最新全套 606 passed、2 skipped，后者是 Windows junction 权限限制。社团重复问候无奖励、收入入口未确认的实际结果仍分别保留停止/恢复未确认，不等同所有业务完成。浏览器原有勾选、顺序和设置已恢复，游戏保留首页，未执行家具或其他资源消费。

登录入口随后增加[条件启动与实机验收](develop/daily_automation.md#登录启动本轮验证)：仅通过已绑定 Maa 控制器只读核对前台 Activity，未在前台时由原生 `StartApp` 启动/切回一次，已打开直接继续，不先强制停止。启动后最多等待已知 UI 120 秒，再复用标题登录/提示清理。CLI 仅对无重启、无消费且已正向回首页的登录恢复允许继续后续项，不放宽其他业务。进程退出后的冷启动→邮箱→好友及已打开→好友→邮箱均有完整成功审计，进程不重复重启；最新全套 638 passed、2 skipped。MPE 旧控制器释放超时后，经用户确认仅重启本项目 LocalBridge，已恢复固定设备的实时首页画面，游戏进程未变；此次未重跑任务，不把连接恢复或旧完成数当作新的串行成功证据。

## 当前 Python 环境与交付

当前新增[项目便携 Python](portable_python.md)：Windows x64 上运行 `scripts/setup_python.ps1` 即可准备 `.runtime/python/python.exe`，不要求全局 Python、Conda 或 Python 的 `PATH`。锁文件固定 Astral Python Build Standalone CPython 3.11.17，以及 MaaFw 5.14.3、numpy、MaaAgentBinary、StrEnum 的版本和哈希；生产应用依赖不含 pytest。开发测试可使用独立 bootstrap/venv，不能把临时验证环境写进 Agent 配置。

源接口使用 `../.runtime/python/python.exe ../agent/main.py`；发布副本改为 `./.runtime/python/python.exe ./agent/main.py`，携带校验后的运行时、许可证与 manifest，不改源接口。启动截图脚本默认使用项目 Python，仅显式 `-CondaEnv` 才走旧兼容路径；缺失不自动回退。发布工作流目标固定 MaaFramework v5.14.3、MFAAvalonia v2.16.2。

2026-10-19 本机已完成私有运行时安装、独立 LocalBridge 默认 Agent 初始化和搬迁后发布包的 Agent IPC 检查；在线 MPE 已重新连接。未创建控制器或 Tasker，未执行游戏任务；GUI 跨机器运行及游戏验收未完成，详细边界见便携 Python 说明的验证记录。下面的初次架构与差距内容保留历史快照，环境现状以本节和便携 Python 说明为准。

## 阅读范围与可验证版本

- 核对日期：2026-10-19。
- 实现仓库：`D:\Codes\MaaNekoConnect`，`main`，HEAD `c8625011be1b8a8d9a2b9428e28c0393ee13ae8d`；开始时工作树干净，无现有 `AGENTS.md` 或 `.agents/skills`。
- 计划仓库：[QuinMeow/MaaNekoConnect_Codex](https://github.com/QuinMeow/MaaNekoConnect_Codex)，经授权 GitHub 读取接口访问，未克隆、下载归档或创建本地计划 checkout。
- 读取 `commits/main` 后固定到提交 [`1e8bd019021a570d1836c39374f624ebfe1d68c3`](https://github.com/QuinMeow/MaaNekoConnect_Codex/commit/1e8bd019021a570d1836c39374f624ebfe1d68c3)，提交时间 `2026-06-14T08:19:31Z`；递归树查询 `truncated=false`。正文通过 `contents/<path>?ref=<该 SHA>` 读取。以下所有计划链接均固定此版本；私有链接需相应权限。

目录核对包括 `.codex/agents/`、`docs/agent-memory/`、`docs/superpowers/plans/`、`scripts/agent/`、环境脚本和外层 `tests/`。重点阅读全文如下：

| 编号 | 计划来源路径（固定提交） | 本文用途 |
| --- | --- | --- |
| P1 | [README.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/README.md) | 项目定位、双仓库、环境入口 |
| P2 | [AGENTS.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/AGENTS.md) | 上游工作规则及本次冲突识别 |
| P3 | [docs/agent-memory/ARCHITECTURE.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/ARCHITECTURE.md) | JSON 优先、仓库边界、记忆流转 |
| P4 | [docs/agent-memory/DECISIONS.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/DECISIONS.md) | 已记录的三项核心决策 |
| P5 | [docs/agent-memory/TASK_BOARD.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/TASK_BOARD.md) | 已勾选基线和后续研究范围 |
| P6 | [docs/agent-memory/PROJECT_CONTEXT.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/PROJECT_CONTEXT.md) | 历史环境快照，须与当前状态分开 |
| P7 | [docs/agent-memory/GAME_KNOWLEDGE.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/GAME_KNOWLEDGE.md) | 2026-06-14 包、Activity、版本与分辨率记录 |
| P8 | [docs/agent-memory/EXPERIMENT_LOG.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/EXPERIMENT_LOG.md) | 历史静态、CI 与实机验证记录 |
| P9 | [docs/agent-memory/STYLE_GUIDE.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/STYLE_GUIDE.md) | 命名、Python 与测试隔离 |
| P10 | [docs/agent-memory/INDEX.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/INDEX.md) | 来源导航及记忆所有权 |
| P11 | [docs/agent-memory/handoffs/README.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/agent-memory/handoffs/README.md) | 交接格式、状态机及冲突处理 |
| P12 | [docs/superpowers/plans/2026-06-14-agent-handoff-memory-governance.md](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/docs/superpowers/plans/2026-06-14-agent-handoff-memory-governance.md) | 五阶段治理实现计划及历史发布待办 |
| P13 | [scripts/setup_workspace.ps1](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/scripts/setup_workspace.ps1) | 外层环境准备实际逻辑 |
| P14 | [scripts/validate_workspace.ps1](https://github.com/QuinMeow/MaaNekoConnect_Codex/blob/1e8bd019021a570d1836c39374f624ebfe1d68c3/scripts/validate_workspace.ps1) | 外层和内层测试、记忆及 MaaFw 检查 |

## 初次核对的架构快照

本节记录最初的启动截图基线；旧裸 `python`、Agent 空壳和单一任务描述不是当前接口配置。

### 任务与设备边界

[`assets/interface.json`](../../assets/interface.json) 声明 interface v2、Android Adb 控制器（短边 720）、默认资源包和唯一任务入口 `TestLaunchAndCapture`。其 Agent 配置为 `python ../agent/main.py`，相对于资源接口所在布局使用；[`tools/install.py`](../../tools/install.py) 打包时会改为 `./agent/main.py`。

[`agent/main.py`](../../agent/main.py) 接收 socket ID，启动、等待和关闭 AgentServer；[`agent/extensions.py`](../../agent/extensions.py) 仅有说明，没有注册自定义识别或动作。现有启动截图流程直接使用 Tasker 与 JSON Pipeline，不经过该 AgentServer，也没有 Python 游戏业务状态机。

### 启动截图链路

```text
scripts/test_nekoconne.ps1
  -> conda run -n maanekoconnect python tools/run_launch_capture.py
  -> 解析 ADB 路径，adb connect 指定地址，pm path 检查游戏包
  -> Toolkit.find_adb_devices，精确匹配目标地址
  -> Resource 加载 assets/resource，AdbController 建立连接
  -> Tasker 绑定资源和控制器，执行 TestLaunchAndCapture
  -> JSON StartApp -> 等待 20000 ms -> JSON Screencap
  -> 检查截图为本次生成的 PNG，宽高为 720×1280
```

实现证据为 [`scripts/test_nekoconne.ps1`](../../scripts/test_nekoconne.ps1) 和 [`tools/run_launch_capture.py`](../../tools/run_launch_capture.py)。2026-10-20 命名整理时已删除正式资源中的 `framework_test.json` 和 Interface 框架测试任务，启动截图诊断流程改由脚本在显式运行时注入。默认地址 `127.0.0.1:5557`，找不到精确设备即报错；允许显式传入地址，但没有自动回退。默认 ADB 候选是代码中的两条 MuMu 安装路径，不能假定在当前电脑存在，应使用真实 `--adb-path` / `-AdbPath`。

控制器固定 `EncodeToFileAndPull` 截图方式。输出为 `debug/screencap/nekoconne_launch.png`。检查覆盖任务成功状态、输出修改时间、PNG 头及尺寸，不包含页面内容识别；固定等待 20 秒不是“已登录”或“首页就绪”的判据。

### 资源、测试与构建

- [`requirements.txt`](../../requirements.txt) 当前固定 `MaaFw==5.14.3`（初次核对时为 5.10.5），另列 `json-with-comments`、`pytest`；CI 使用 Python 3.11。
- [`tests/test_project_config.py`](../../tests/test_project_config.py) 检查单一任务、Pipeline、模板示例清理、CI 和打包路径；[`tests/test_run_launch_capture.py`](../../tests/test_run_launch_capture.py) 检查设备精确选择、禁止回退、截图方式、PNG 头及包检查目标。它们不是实机验收；其中一项需要导入 MaaFw 枚举。
- [`check.yml`](../../.github/workflows/check.yml) 安装依赖后做 Schema 校验、`compileall`、pytest；Schema 目录为 `deps/tools`，不能直接使用校验脚本默认的 `tools/schema`。
- [`tools/configure.py`](../../tools/configure.py) 从 MaaCommonAssets 复制中文 OCR 模型；当前 launch Pipeline 未使用 OCR。`assets/MaaCommonAssets` 是真实 Git submodule（HEAD 记录 `9adc92ed264318c4d13dcf6df4565c746169a20e`），与“计划仓库和实现仓库不是 submodule”是两回事；当前目录为空，未初始化资源。
- [`install.yml`](../../.github/workflows/install.yml) 在 Ubuntu runner 上为 Windows x64 打包。初次核对时 MFAAvalonia 取 latest，现已固定 v2.16.2，并先准备项目 Python；`tools/install.py` 要求已准备原生 deps、Agent 运行时和所用 OCR 模型。不能把发布链定义视为本机产物已可运行。
- [`package.json`](../../package.json) 只有开发依赖，没有 npm scripts；[`maatools.config.mts`](../../maatools.config.mts) 当前已固定 `maaVersion: '5.14.3'`，与 Python/发布版本一致。初次核对时的 latest 偏差已在后续框架同步中修正，见 [框架更新记录](develop/maa_framework_updates.md)。

## 计划中的决策及先后关系

1. **先维持仓库边界和可复用框架。** P1、P3、P4：计划仓库存编排与研究，实现仓库存应用；默认 JSON Pipeline 和框架 API，复杂状态或数据处理确有必要时再加入 Python。
2. **先确认设备，再扩大业务流程。** P4、P5、P7：默认仅 `5557`，基线为启动截图。包、Activity `com.google.firebase.MessagingUnityPlayerActivity`、游戏 1.4.2 都是 2026-06-14 的记录，本轮未探测设备或版本。
3. **证据先于长期记忆。** P3、P4、P10、P11：子 Agent 报告经主协调代理记录，原始报告不可覆盖；`proposed -> reviewed -> promoted|rejected`，晋升文字由协调者显式选择并保留 `Source-Handoff`。这是外层治理设计，不是游戏运行时架构。
4. **治理实现的明确顺序。** P12：先定义并测试 handoff 契约，再实现记录/晋升，然后接入校验、分配写入所有权，最后验证和发布。计划勾选了前述实现与验证，但仍保留“push 被网络配额阻止”的未勾选历史条目；该文档已存在于读取到的远程提交，不能据此断言今天仍未推送。
5. **接下来研究实际游戏流程。** P5 只写持续补充游戏知识与实验记录。基于当前缺口，建议未来先复核目标设备和截图基线，再选一个明确业务目标，采集页面和异常证据，定义识别与恢复流程、测试及验收，最后逐项扩展。此为本文建议，并非上游既定玩法排期。

## 初次核对的差距快照

| 领域 | 当前代码或来源能够证明的内容 | 尚不能证明或仍缺失的内容 |
| --- | --- | --- |
| 启动与截图 | 单一 JSON 链路、精确设备匹配、无损截图参数、输出检查 | 当前 PC 实际成功、画面有效、加载完成；本轮未实机运行 |
| 游戏任务 | 仅启动截图任务 | 登录、弹窗处理、首页识别、日常玩法、战斗等均无对应流程；是否纳入范围待用户确定 |
| 扩展能力 | AgentServer 启动壳、扩展文件 | 自定义动作/识别和业务恢复逻辑尚未实现 |
| 测试与验证 | 离线测试代码、Schema、Windows check CI 定义 | 当前依赖环境下全套测试通过；已有测试不检验游戏视觉内容 |
| 环境准备 | P13 定义外层 Conda/子模块/OCR setup | 本 checkout 没有该外层脚本，也没有可确认已就绪的专用环境和 OCR 资源 |
| 打包发布 | 原生依赖和 MFA 组合的 Windows x64 工作流 | 当前产物可用性、可重现的 MFA 版本和实机回归 |
| 编排与长期记忆 | 上游存在相应计划、脚本目录与历史记录 | 它们不是当前实现 checkout 的组成部分，不应复制外层状态为本地事实 |

## 历史记录与冲突处理

- P6 的自动状态仍是 `codex/bootstrap-framework`、提交 `868a76538adead47fd30d43ad819213fc8913376`，生成于 2026-06-14；本地实际为上述 `main` 与 `c862501…`。设备 online 和 Conda 环境存在也只能算历史记录。
- P8 先记录一次实机验证未完成，后追加同日成功：MaaFw 5.10.5、`5557`、720×1280、1,010,056 字节，截图 SHA-256 `a6ecc6e29cccd548a7304b8411bfbe8e501373668055519f13b74a6c6056b333`；并解释默认 EmulatorExtras 曾黑屏，改用 `EncodeToFileAndPull` 后解决。代码与该修正一致，但本轮未获取或复验原截图。
- P8 记录 PR #1 的 `cf330c5` 曾通过 check 和 Windows x64 install。它是历史 CI 记录，不是当前 HEAD 或本轮测试结果。
- P1、P2 的路径假设为外层嵌套内层，P2 还禁止内层跟踪 `AGENTS.md` 并要求推送才完成。本次用户明确指定独立 checkout、创建根 AGENTS 且不提交/推送，因此以当前要求为准；不迁移 Git 元数据，不克隆外层，不执行其 snapshot、handoff 或发布流程。
- 现有 [开发教程](develop/how_to_develop.md)、[个性化配置](develop/custom_configure.md)、[FAQ](develop/faq.md) 多为模板说明，包含新建仓库、发布、多平台及 pre-commit 指引；checkout 没有 `.pre-commit-config.yaml`。实际开发命令以 [根 AGENTS.md](../../AGENTS.md) 和当前 CI 为准，不因模板文字安装工具或发布。

## 仍待确认的问题

1. 首个业务目标是什么，登录/首页/日常流程各需支持哪些页面和成功判据？上游没有玩法路线图。
2. 当前设备地址、ADB 路径、账号状态、游戏版本、语言与分辨率是否仍与六月观测一致？后续实机任务需重新确认。
3. 长期生产环境现由项目便携 Python 和哈希锁准备，不再沿用外层 Conda 或临时环境；实际 MPE Agent 启动和搬迁后运行仍应单独验收。
4. 独立项目如何持续同步上游计划与研究记录，哪些结论应留本仓库、哪些仍在私有编排库维护？本轮仅形成固定版本对照，不建立自动同步机制。
5. maa-tools 与固定 MaaFw 版本已统一为 5.14.3，MFAA 已固定为 v2.16.2；后续升级需同步锁与验收，语义截图和实机交付仍不能只靠版本固定证明。

## 初次文档整理的验证与边界

- 仅新增本文和根 `AGENTS.md`；未改功能代码、依赖或现有说明，未执行游戏自动化、安装、提交或推送。
- 实际可调用的默认 Python 为 3.10.9，检测缺少 `pytest`、`maa`、`jsonschema`、`referencing`、`jsonc`；`conda env list` 返回系统无法执行指定程序，未确认专用环境。
- 尝试 `python -m pytest -q` 因缺 pytest 不能运行；Schema 命令因缺 jsonschema 不能运行。`compileall` 重定向缓存到临时目录时遇到写入/重命名权限错误；改用内存 `compile()` 检查 `agent/`、`tools/`、`tests/` 共 8 个 Python 文件，语法通过，此结果不替代 Python 3.11 下的完整 CI。
- `git submodule status` 遇到 Git shell 的 Windows 命名对象访问错误；改用 `git ls-tree HEAD assets/MaaCommonAssets` 核对 gitlink，并读取目录确认资源未展开，未执行初始化。
- 本地相对链接、14 条固定提交的计划文件路径、UTF-8/LF 和 JSON 基线检查通过。`git diff --check` 通过；另对两份未跟踪新文档执行无索引空白检查，无空白错误。最终状态仅有这两份新增文档，HEAD 未变。完整行为验证的阻塞是本机依赖和环境未就绪，文档工作不依赖启动游戏完成。
