# 家具强化：单轮补位与间隔调度（实验功能）

## 模块与官方约定

本项目使用 MaaFw 5.14.3。按[官方快速开始](https://maafw.com/docs/1.1-QuickStarted/)的 JSON + 必要 Custom 方式实现；资源加载会递归读取 pipeline JSON，拆文件不需要重新编译。[Pipeline 协议](https://maafw.com/docs/3.1-PipelineProtocol/)定义有序 next、组合识别、锚点和 max_hit；[PI V2](https://maafw.com/docs/3.3-ProjectInterfaceV2/)负责声明任务与参数，不是完成后间隔调度器。这里的业务前缀是本项目约定，不是官方强制命名规范。

| 模块 | 职责 |
| --- | --- |
| [navigation.json](../../../assets/resource/pipeline/navigation.json) | NavHome_* 返回首页；NavSoleil_* 进入咖啡店。页面到达正向确认、调用方返回锚点，见[契约](navigation.md) |
| [furniture_filter.json](../../../assets/resource/pipeline/furniture_filter.json) | FurnitureFilter_*：Lv 排序、仅已配置、仅可升级，复选框幂等确认 |
| [furniture_enhance.json](../../../assets/resource/pipeline/furniture_enhance.json) | FurnitureEnhance_*：进入强化页、单轮最多 5 次普通强化尝试、重新扫描、轮末退出 |
| [soleil_shop.json](../../../assets/resource/pipeline/soleil_shop.json) | Soleil_*：咖啡店依頼，一轮至多尝试点击一次 |
| [furniture_schedule.json](../../../assets/resource/pipeline/furniture_schedule.json) | FurnitureSchedule_*：有限轮数，首轮立即执行，后续轮前等待 |
| [furniture_timer.json](../../../assets/resource/pipeline/furniture_timer.json) | FurnitureTimer_*：选择可见忙碌家具、确认选中、原生 OCR、等待接入 |
| [common_recovery.json](../../../assets/resource/pipeline/common_recovery.json) | 共用[网络、冻结和有界重启](common_recovery.md) |
| [agent/furniture_timer.py](../../../agent/furniture_timer.py) | 严格解析时间、min/max 计算、Context 局部状态及可取消分段等待，不实现选家具状态机或图像比较器 |

对外入口为 FurnitureSchedule_Start，独立单轮入口为 FurnitureEnhance_Round。原 SoleilUpgradeLoop 只保留兼容转发，不再包含业务。PI 旧 task.name 保留为配置 ID，显示名与节点名区分咖啡店、强化、筛选、调度。编辑单个模块时仍需加载完整资源，不能只加载兼容文件运行。

## 单轮行为

```text
确认强化页（需要时：首页 -> Soleil 咖啡店 -> 强化）
  -> 保留当前排序/筛选，或应用指定排序/筛选 -> 回顶
  -> 有序检查前五格：忙碌锤子优先；有候选提示才选择
  -> 本格红边 + 普通强化按钮 + 页面/回顶门禁
  -> 消费前再次识别 -> 尝试普通强化 -> 确认“時短”
  -> 从第 1 格重新扫描（列表可能重排）
  -> 已尝试 5 次，或前五格无候选：本轮结束
  -> 本轮至少 1 次确认启动且开启依頼：返回店铺，依頼一次
  -> 返回调度器；最后一轮直接结束，不多等一个间隔
```

不要求五件全部空闲，也不强求本轮凑满五件；有空位就补。每次确认后重扫是**有 5 次上限的轮内循环**，不在强化模块里无限等待。橙色 ! 不是空闲证明，忙碌家具也可能保留它。扣券节点只单击一次，不使用 repeat；组合识别复用 ReadyN 不会执行它的 action/next。

单轮使用 6 个原生锚点许可状态，正常新轮才初始化，恢复不能重置。CLI 的 SessionSpendPermit 总消费上限、调度总轮数和通用恢复预算都跨轮保留。不确定的消费尝试也占额度。扣券后只检查详情“時短”，不要求格子仍在原位置，以容许游戏重排。

依頼只在轮末尝试，不再逐件退出；无新增确认则不点。请求前已把恢复锚点切到本轮完成，即使点击失败、网络中断或提示瞬间消失也不盲目重发。点击完成不承诺援助到账、服务端受理或强化完成。

## 配置与时间

| 选项 | 默认 | 说明 |
| --- | --- | --- |
| 使用现有排序 | 开 | 不检查/改变排序和筛选，但仍回顶；不保证最低等级 |
| Lv 升/降序、仅已配置、仅可升级 | 升序、开、开 | 关闭现有排序后条件显示；配置前重置游戏原筛选 |
| 本轮结束后点击依頼 | 开 | 独立选项 |
| 运行方式 | 仅运行一轮 | 另可选固定间隔、最短剩余时间、最长剩余时间 |
| 总轮数 | 1 | 含立即执行的首轮，1..10000；只在间隔模式显示 |
| 固定／回退间隔 | 60 秒 | 10..86400 秒；只在间隔模式显示 |

运行方式和间隔分别通过 FurnitureTimer_Config 与 FurnitureTimer_IntervalConfig 写入。MFAA 会按顺序提交选项覆盖，而 MaaFramework 的 custom_action_param 是整个字段替换，不会递归合并；不能在同一节点先设 mode，再仅覆盖 seconds，否则会丢失 op/mode。这里使用独立节点，每份参数都包含完整 op，见[固定版解析实现](https://github.com/MaaXYZ/MaaFramework/blob/v5.14.3/source/MaaFramework/Resource/PipelineParser.cpp)。

最短/最长是依頼后**当前列表可见前五格中忙碌家具**的预计最早/最晚完成时间，不是全局强化队列。JSON 逐格选择，确认本格红边、“時短”和明亮页面后，由 MaaFramework 原生 OCR 读取 HH:MM:SS（置信度至少 0.9）。以采样时刻 + 秒数求预计完成时刻，修正多格串行读取耗时。最后提交的等待至少 10 秒，避免临界完成时忙循环。

没有可见忙碌家具、读数缺失/低置信度/格式无效或采样中页面改变时，不取不完整读数猜 min/max，使用配置的固定间隔。状态在当前 Task 的 Context 内，不用跨任务全局字典。恢复续等不重新领取轮次许可，也不无限延后已提交 deadline；日志中的 timer state 记录 fallback 及原因。

固定模式不需要 OCR 权重。动态模式需要 model/ocr/det.onnx、rec.onnx、keys.txt；本机开发目录已从安装好的 LocalBridge 复制到忽略目录验证。发布仍使用 [tools/configure.py](../../../tools/configure.py) 配置 MaaCommonAssets 的 OCR，不能依赖本机安装路径或把开发副本存在误当作发布包已完成。

等待不是长 post_delay，也不依赖 MFAA 私有 CountdownAction。短段检查停止和已知网络；合法忙碌预览使用原生连续 30 秒 timer ROI 冻结观察，最长单次 35 秒。局部冻结后重新确认本格/页面；新 Loading 必须交公共恢复重新观察，不能沿用旧局部证据重启。正常静态空闲不跑冻结探针。取消可能受原生观察超时影响，不承诺即时退出。

## 运行与停止

需要 Python 3.11、requirements.txt 的 MaaFw 5.14.3。目标默认仅 127.0.0.1:5557，不回退。示例 ADB 是本机观测路径。

单轮、整个运行最多尝试启动 1 件：

```powershell
$env:PYTHONUTF8 = "1"
python tools/run_soleil_upgrade.py --execute --max-starts 1 --adb-path "C:\Program Files\NetEase\MuMu\nx_main\adb.exe"
```

显式运行 3 轮，轮间按可见最短剩余时间，读取失败等 60 秒：

```powershell
python tools/run_soleil_upgrade.py --execute --rounds 3 --wait-mode shortest --interval 60 --adb-path "C:\Program Files\NetEase\MuMu\nx_main\adb.exe"
```

最长用 longest，固定用 fixed。默认仅一轮；--one-pass/--one-batch 是兼容参数，也限定一轮。--max-starts 1..5 是**整个运行**硬上限，不是每轮限额；不传时 CLI 总上限为 5 x 轮数。Ctrl+C 停止 Tasker，不取消游戏里已开始的强化。缺少 --execute 或参数无效时不调用 ADB。

--configure-sort 默认 Lv 升序、仅已配置、仅可升级；可加 --sort-order lv_desc、--all-furniture、--include-unupgradeable。这些排序参数要求显式 --configure-sort，防止隐藏设置被误当作应用；--no-auto-request 独立可用。选项映射由 [soleil_options.py](../../../tools/soleil_options.py) 提供，与 PI 一致。

CLI 审计全部轮次、累计许可、每轮最多 5 次、共享启动确认、轮末依頼至多一次及恢复完整性。任何未确认消费即使恢复后到达终点仍非零，不用“任务成功”掩盖未知服务端结果。MPE 原始入口不会自动解析 PI 用户配置；要注册 WaitForFrozenScreen 和 FurnitureTimerControl 扩展。CLI 直接注册 Resource，不导入 AgentServer；MFAA 通过 agent/extensions.py 注册。GUI 执行同样会扣券。

## MPE 与复用

在线 MPE + 独立 LocalBridge 继续为默认编辑方式。查看上述各模块的真实本地文件；不要用 config 导出覆盖源文件或未保存画布。修改 JSON/图像后停止任务、保存、重载资源即可，不承诺运行中热更新。Python 扩展修改还需重启 Agent/调试任务，已安装客户端也要同步资源和脚本。

通用导航只保证已知页面的正向到达，不夹带强化、依頼或消费。调用方绑定 NavHome_Return / NavSoleil_Return，并持有 CommonRecoveryResume；导航不覆盖业务恢复点。锚点不是函数调用栈，嵌套调用要显式重绑。And/Or 引用只复用识别，不继承节点级 inverse、动作或流程；JumpBack 返回父节点的 next，不是重做父动作。上述语义应以固定版本和原生回归为准。

## 验证边界与历史

2026-10-19 此次重构验证单轮 0/1/3/5/超过 5 个候选、轮末一次依頼、请求失败不重发、消费失败不退额度、跨轮预算、OCR 解析/回退/停止、导航明亮与遮罩负例。测试使用无真实输入的 CustomController 和 UI 裁剪夹具；本次没有新增实机扣券、依頼或长时调度验收。截图、单张 OCR 成功和离线通过都不证明实机跨账号/版本泛化。

测试精简前的检查点为 658 项 pytest 通过（76.46 秒，无跳过），不是轻量测试规范调整及 MFAA 参数修复后的当前用例数量。当前测试组织和验证边界见[测试说明](../../../tests/README.md)。本机已配置模型并执行过原生 OCR；其他 checkout 缺少模型时，该部分会明确跳过，不能沿用本机结果。

重构前最后一次授权实测：2026-10-19 19:11:43 至 19:13:58，5 次普通强化均获“時短”确认，当时仍为旧逻辑的 5 次逐件依頼，0 恢复、0 重启，运行器退出 0。日志 debug/soleil-execute-20261019-191143.log；本次核对图 debug/soleil-execute-20261019-191143-verified.png 可见五格锤子及余额 19080。它不验证本次“轮末依頼一次”与动态等待。

更早的两次 Loading 失败没有取得启动确认，不能断言服务端未受理。零消费网络恢复及受控单次重启后到首页曾通过，但不是现场诱发冻结实测。旧整批 Lv 升序在 13:02:45 通过一次五件启动；这些历史结果与旧 516 项回归数均不替代本次结果。

普通费用/时长仅为游戏 2.2.0、JP2、720 x 1280 于 2026-10-19 的观测：Lv3 -> Lv4 的一件显示 20 券/8 分钟，Lv4 -> Lv5 的一件显示 20 券/11 分钟，不是所有家具的固定值。流程不付费加速、不购买材料、不开槽；未知通知、活动或其他弹窗不猜点。屏幕外任务占位时可能无法启动，最终由有界恢复停止。

模板与夹具来源见 [Soleil 夹具](../../../tests/fixtures/soleil/README.md)、[导航夹具](../../../tests/fixtures/navigation/README.md)和[恢复夹具](../../../tests/fixtures/recovery/README.md)。合成忙闲/重排画面是回归测试，不是独立实拍。
