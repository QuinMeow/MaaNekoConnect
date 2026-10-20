# 通用异常恢复（实验功能）

## 设计边界

[common_recovery.json](../../../assets/resource/pipeline/common_recovery.json) 集中处理已识别的登录失败退出、网络、跨日、访问拒绝、游玩设备确认弹窗、Loading、标题页、首页和有界重启。业务导航、确认和消费仍由各自 Pipeline 决定，恢复层不点击普通强化、不购买材料、不重放未确认的消费动作，也不连接其他设备。

主要逻辑为 JSON；[agent/recovery.py](../../../agent/recovery.py) 只有一个极薄的 `CustomRecognition`：`WaitForFrozenScreen`。通常它校验参数后调用一次 MaaFramework 原生 `context.wait_freezes(wait_freezes_param=JWaitFreezes(...))`，只有返回值严格为 `True` 才返回 `AnalyzeResult`；`False`、参数错误、异常、超时或停止都不命中。不重做图像比较算法，没有后台 watchdog 或扩展内点击/重启。唯一的全黑帧退化例外见下文。

不要直接把 `pre_wait_freezes` 配在重启动作上作为“确认冻结”的条件。MaaFramework v5.14.3 的这些字段是动作前后等待钩子，`TaskBase::wait_freezes` 的 `void` 包装不向流程传递成功与否；等待结束不等于已获得冻结证据，见 [固定版本 TaskBase](https://github.com/MaaXYZ/MaaFramework/blob/v5.14.3/source/MaaFramework/Task/TaskBase.cpp#L104)。`Context::wait_freezes` 则返回原生布尔结果，适合通过这个识别桥进入 JSON 的命中/未命中分支，见 [固定版本 Context](https://github.com/MaaXYZ/MaaFramework/blob/v5.14.3/source/MaaFramework/Task/Context.cpp#L137)。

## 恢复路径

```text
业务超时/动作失败/已知异常中断 -> CommonRecoveryEnter -> 恢复预算
  -> 登录失败退出/游玩设备确认/访问拒绝/跨日/网络：专用 Gate -> 有界 Confirm 或截图停止
  -> 登录失败 OK 后：原共享重启许可 -> 有界重启；不使用通用 Close
  -> 返回标题或设备确认后重新判页，不点击底层 Close
  -> Loading：先观察，不因标题文字同时可见而重复点击标题
  -> 标题 Logo + TAP：点击进入，再判页
  -> 首页建筑与标签就绪：恢复完成 -> 业务安全恢复锚点
  -> 其他状态：原生观察30秒 -> 有变化则重新判页
  -> 确认静止：重新检查当前画面，优先处理新出现的网络/首页/标题状态
  -> 仍需重启：重启预算 -> 截图 -> 停止并启动精确游戏包 -> 重新判页
  -> 预算耗尽/动作失败/无法安全继续：截图并 StopTask
```

最初支持的是 2026-10-19 720 x 1280 日文界面中已观测的“返回标题”网络错误弹窗，后续新增日期变化、访问拒绝、游玩设备确认、登录失败退出和通用登录提示清理，见下节。已知错误仍要求专用消息与对应按钮同时命中，设备确认和登录失败另要求各自标题；这些分支优先于通用关闭。错误提示下方的 Close 不是该提示的确认按钮。非这些特殊情况时，允许识别通用 Close 或点击继续，不再要求公告标题或具体活动名称。

Loading 的省略号会变化，生产模板只截取静态 `Loading` 字样，没有靠降低阈值适配动画。标题页 Loading 时也可能保留 Logo 和 TAP，故 `Loading` 分支须优先于标题点击。冻结等待返回后重新判页，防止在观察期间恢复到首页或出现已知网络弹窗后仍沿用旧画面重启。

业务已经点过首页入口、却无法离开首页时，不能走“首页就绪即恢复成功”的普通路线。Soleil 的该失败入口为 `CommonRecoveryHomeStallEnter`：先观察首页，再经 `CommonRecoveryHomeFreshCheck` 重新检查；若确认仍是冻结首页才进入重启预算，避免同一张首页被反复当作健康恢复而绕开卡死检测。

`CommonRecoveryBudget.max_hit=3` 限制一次 Task 内累计进入恢复最多 3 次，`CommonRecoveryRestartPermit.max_hit=2` 限制累计重启最多 2 次。标题点击和冻结观察许可也各有限额 3；五类错误确认限额见下表。成功回到业务后**不清零**，不会通过循环回入口或重载资源重置计数。新建另一个 Task 是新的计数边界，不应被调用方用作无限重试方式。

只有 JSON 的 `CommonStopGame` / `CommonStartGame` 执行应用重启，包名均精确为 `jp.goodsmile.nekoconne`；不停止模拟器、ADB 服务或其他应用。重启前截图为 `debug/screencap/common_recovery_before_restart.png`，终止截图为 `debug/screencap/common_recovery_stopped.png`，随后执行 `StopTask`。框架任务状态或截图成功不能替代业务结果审计。

## 跨日、设备冲突与登录提示

2026-10-19 23 点后的[实机探索](daily_observation_20261019.md)补充「日付が変わりました」分支。日期消息与「タイトルへ」按钮同时命中才点击，不能使用底部被遮挡的 Close。该情况进入原有恢复预算，返回标题、登录、清理已知提示并正向确认首页，再回 `CommonRecoveryResume` 安全入口。日期按钮累计最多 3 次，不重置消费、调度或恢复预算，不直接重放中断业务。

同日 23:43 用户手机登录后，本机返回主页时观测到「ゲームサーバへのアクセスが拒否されました。」和「タイトルへ」。这不是普通公告或网络错误的通用 Close；`CommonAccessDenied*` 识别专用正文并复用现有标题按钮模板，点击 `[345,653,30,25]` 后进入原 `CommonRecoveryDispatch`。23:47 的下一张截图出现「プレイ端末の確認」，正文说明其他设备正在游玩，并询问是否在本设备接续/联动游玩。`CommonPlayDevice*` 必须同时识别该标题、正文和 OK 按钮，才点击 `[345,823,30,25]`。本轮用户明确停止手机操作并允许继续本机探索；这项确认不代表检测到其他设备后可以无限抢登。完整观测与素材索引见[每日任务探索](daily_tasks_research.md)。

2026-10-20 11:06:24 的 `debug/on_error/2026.10.20-11.06.24.427_Daily_FriendMenu.png` 新增「ログインに失敗しました」标题及「サーバーへの接続に失敗しました / ゲームを終了します」正文。虽然提到服务器连接，它是要求退出游戏的独立 `CommonLoginFailed*` 类型，不能当作原有“返回标题”网络错误、设备确认或普通关闭提示。生产标题裁剪为 `[225,295,270,40]`、正文为 `[195,375,330,60]`，OK 复用 `CommonPlayDeviceButton`。标题、专用正文、OK 三者同时命中才允许确认；同一 Task 最多一次，随后进入原 `CommonRecoveryRestartPermit`，与其他恢复路径共享累计最多两次重启，不能领取新的恢复或消费预算。

当时通用 Close 曾误处理覆盖其上的登录失败提示，之后有界重启停在启动器；新增专用分支及优先级后尚未实机复验。确认耗尽、重启预算耗尽或无法再判页就截图停止，不点底层 Close、不重放中断的好友或其他业务。首次独立每日批次的停止报告及未运行后续项见[每日自动化说明](daily_automation.md)。

| 已识别情况 | 必要门禁 | 每 Task 累计确认上限 |
| --- | --- | --- |
| 网络错误 `CommonNetworkConfirm` | 专用网络正文 + 返回标题按钮 | 3 |
| 日期变化 `CommonDateChangedConfirm` | 日期正文 +「タイトルへ」 | 3 |
| 访问拒绝 `CommonAccessDeniedConfirm` | 访问拒绝正文 +「タイトルへ」 | 3 |
| 游玩设备确认 `CommonPlayDeviceConfirm` |「プレイ端末の確認」标题 + 专用正文 + OK | 1 |
| 登录失败退出 `CommonLoginFailedConfirm` |「ログインに失敗しました」标题 + 退出正文 + OK | 1 |

五类错误均采用**无次数上限的纯识别 Gate -> 有界 Confirm / `CommonRecoveryStopCapture`**，而不是直接把有限额 Confirm 放在通用关闭之前。当前 MaaFramework v5.14.3 离线测试复现：`max_hit` 耗尽会跳过该节点，不会触发它的 `on_error`；旧结构会落入仍可见的底层 Close。专用 Gate 在错误仍可识别时截住流程；确认次数耗尽或再次识别失败就截图并停止，不尝试通用 Close、不额外抢登、不清零任何许可。设备确认或登录失败再次出现时不再点 OK。

`CommonRecoveryDispatch` 以及冻结后的两种 fresh-check 均先检查登录失败、设备确认、访问拒绝、日期、网络和 Loading，再使用[导航模块](navigation.md)中的通用 Close、继续提示和奖励外框，重新判页后才视为首页或允许重启。关闭许可是整个 Task 共享的 20 次，不因回到 Dispatch 续期。新活动沿用通用 UI 时无需逐活动维护；未识别到任何通用控件或外框则不无条件盲点。

新增提示均有离线原生识别和模拟恢复测试，包括访问拒绝 -> 游玩设备确认 -> 标题 TAP -> 正向首页 -> 调用方安全入口，以及五类错误持续出现时的 3/3/3/1/1 上限、移除任一必要标记、底层 Close 可见时不穿透。登录失败另覆盖 OK 后共享重启和恢复返回，不重放业务。实机提示观察或手动处理不等于新增自动全链验收；自动跨日、登录失败修复与偶发主页重弹仍不能用模拟结果代替。

## 冻结参数与业务等待

全屏观察默认参数为：

```json
{
  "time": 30000,
  "target": [0, 0, 0, 0],
  "threshold": 0.000001,
  "method": 1,
  "rate_limit": 1000,
  "timeout": 35000
}
```

`time` 表示连续满足原生画面稳定判据的时长，不是固定睡眠后无条件重启；`timeout` 是该次原生观察的上限。外层 `timeout` 限制当前节点对后继的扫描，不能中断已经进入的自定义识别回调。扩展只允许上述六个键，拒绝无限超时、布尔值冒充整数、非有限阈值、不支持的方法、无效/溢出矩形和等待时长超过超时。测试可以使用短时参数，但不改变生产默认值。

取消不是 Python 强制中断原生调用：通常停止控制器会令截图失败而提前返回，但不能承诺即时完成，最坏需等待原生观察按所配 35 秒超时返回。短时原生回归分别停止静态和动态画面，记录识别回调实际返回 `None`，而不是只看任务取消状态；这不替代不同设备或传输故障下的取消时延验收。

`method=1` 使用原始 `SQDIFF_NORMED` 差异分数，**越低越好**，只有 `score < threshold` 才算稳定，不是 `1-threshold` 相似度。`0.9999` 比 `0.9995` 更宽松而非更严格；生产全屏差异阈值为 `0.000001`。判断方向以 [固定版本 TemplateComparator](https://github.com/MaaXYZ/MaaFramework/blob/v5.14.3/source/MaaFramework/Vision/TemplateComparator.cpp) 为准，不能套用其他匹配方法的高相似度阈值。阈值为 0 时，连差异分数 0 也不满足严格小于，不应作为冻结参数。

“画面稳定”是原生模板差异阈值的判断，不是逐像素完全相同的保证，也不读取业务语义。全屏装饰动画可能掩盖业务卡死，小范围数字变化也可能被容差忽略；不同 ROI 和阈值需要独立验证，不能把一张静态夹具的成功泛化到所有计时场景。

家具调度的合法忙碌页也需要防卡死：[计时模块](soleil_upgrade.md)选择可见忙碌格后，用原生等待观察倒计时 ROI `[520, 1000, 125, 65]`，而不是整页装饰动画。当前使用 `threshold=0.000001`、`method=1`，不重新实现比较器。局部稳定后必须重新判页，不能把“此 ROI 没变”当成“当前整页已经冻结”。出现网络弹窗先处理；出现 Loading 则交公共恢复重新观察全屏；强化已结束恢复普通按钮时继续正常等待；只有仍正向确认同格选中、明亮强化页和“時短”才使用局部冻结证明进入恢复。OCR 只为最短/最长间隔计算服务，冻结判断仍使用原生图像差异，不从旧读数推断屏幕外队列。

没有可见 Busy 时，包括正常静态的全空闲强化页，不运行倒计时冻结探针，也不因正常页面静止而重启。等待使用 Context 中已提交的 deadline，恢复不重新领取调度许可或重置截止时刻；原生观察的单次最长 35 秒仍可能影响停止时延，不承诺即时取消。

### 全黑帧例外

原生短时测试复现了归一化匹配的零能量退化：恒定全黑画面不会命中冻结，而近黑值 1、灰色 128 和白色 255 可以命中。为避免合法黑屏卡死永远不进入恢复，仅当目标是全屏 `[0,0,0,0]` 且初始图为非空 `uint8` BGR 全零时，扩展使用一个最小例外：按单次调用局部的 `monotonic` 时间，调用控制器 `post_screencap().wait()` 并检查成功，再读取 `cached_image`，确认连续 `time` 都是同尺寸全黑。

此例外按 `rate_limit` 采样并受 `timeout` 约束，每次截图前后检查 `tasker.stopping`。任意非黑、空图、尺寸/格式变化、截图失败、读取异常、停止或超时立即不命中，黑白交替不能被当作持续黑屏。它不估算差异、不点击、不重启；普通非黑画面和局部 ROI 仍只使用原生 `wait_freezes`。这里的短时采样循环只修补全黑零能量边界，不是常驻 Python watchdog。

## 接入其他业务

### 串行任务的纯导航

2026-10-20 起，`NavHome_Ensure` 与日常收尾 `Daily_Return` 共用 `NavHome_Normalize`。它正向识别首页、Soleil、强化页，以及 Quest、地图、VR、比赛、交换、礼物、备战、卡池和社团/成员页；只有已知业务页和明亮 Home 同时成立才点击 Home。菜单、好友、每日列表、邮箱、容量不足、社团帮助/赞助和普通奖励使用关闭动作，不调用这些页面的问候、领取或消费后继。

入口与收尾分别绑定私有 `NavHome_NormalizeReturn`，不覆盖业务的 `NavHome_Return` 或 `Daily_AfterWork`。到达首页须重新确认 `NavHome_Ready` 后才交还调用方，不能继承前一个 Task 的业务返回点。点击 Home 后进入独立 `NavHome_AwaitHome`，不再扫描原业务页来重点击；无效点击或未知页面等待超时即截图停止，不重启正常静态业务页。Home 动作每 Task 共享上限八次，弹窗沿用每 Task 二十次共享关闭许可，恢复不重置预算。

登录失败、其他设备登录、访问失效、跨日、网络错误和 Loading 优先于普通 Close。公共恢复在 Watch/Restart 前增加已知正常页面分流，通过同一个纯导航返回后再进入原有安全恢复点，不重放所选业务。既有冷启动、黑屏及未知冻结恢复仍保留原有有界逻辑；战斗中、未知确认框和 SDK 广告不属于普通页面返回许可。

业务应在安全入口配置 `CommonRecoveryResume` 锚点，并将异常后继指向 `CommonRecoveryEnter`，例如：

```json
{
  "ExampleTaskEntry": {
    "recognition": "DirectHit",
    "anchor": {"CommonRecoveryResume": "ExampleSafeResume"},
    "next": ["ExampleBusinessPage"],
    "on_error": ["CommonRecoveryEnter"]
  },
  "ExampleSafeResume": {
    "recognition": "DirectHit",
    "next": ["ExampleTaskEntry"]
  }
}
```

这是接入结构示意，不是可直接执行的完整任务；示例业务节点需由调用方定义并加页面门禁。恢复层通过 `[Anchor]CommonRecoveryResume` 返回，锚点必须是能重新确认页面与业务状态的安全入口，不应指向扣券、购买或其他不可盲重试动作。业务还需保留未确认消费的“不确定”结果，不能因网络恢复后任务最终到达正常终点就抹除先前未确认的请求。

MFAA AgentServer 通过 [agent/extensions.py](../../../agent/extensions.py) 导入时注册该识别。直接使用 `Resource` 的 CLI 则调用 `register_recovery(resource)` 后加载资源；注册失败抛出错误，不静默继续。普通 Framework 运行进程只导入 `recovery`，不要导入 `extensions` 或 `maa.agent.agent_server`；SDK 的 AgentServer 包会选择独立进程使用的原生库模式。

## 验证边界

[恢复模块测试](../../../tests/test_recovery.py) 合并扩展、识别和流程用例，验证严格布尔分流、无效参数拒绝、连续黑帧边界、原生静态/变化画面、恢复 UI 门禁、错误确认耗尽后停止而不穿透 Close、冻结后重新判页和累计重启预算。遵循[轻量测试约定](../../../tests/README.md)，不再分别维护结构、流程和视觉测试文件。

历史倒计时探针曾在内存里将 `active_timer.npz` 的末位数字平移 1 像素，高差异阈值 `0.9995` 和 `0.9999` 漏掉变化，原生差异分数为 `0.000468`；旧版收紧到 `0.0001` 后通过，当前计时模块参数为 `0.000001`。另有 ROI 外 Loading 移动的历史序列说明局部冻结不等于全屏冻结。这些完整矩阵已在精简时移除，不作为当前回归覆盖声明；当前保留冻结后重新判页的行为测试，不保证所有微小变化都被检测。

全黑例外的 fake-clock 用例保留连续全黑、帧变化、停止、超时和失败截图；空图和回调异常均须拒绝恢复授权。未包含任何真实设备输入。

恢复 UI 识别样本来源和裁剪边界见[恢复夹具说明](../../../tests/fixtures/recovery/README.md)。流程测试只模拟目标游戏的停止与启动，不操作真实设备。模拟输入、短时原生等待、静态夹具和完整实机恢复是不同层次的证据。

2026-10-19 曾有 516 项历史检查点；本次精简前基线为 658 项通过。这些数量不是精简后当前覆盖规模，也不能全部称为原生视觉或实机测试。当前只保留代表性行为和关键安全边界。

同日零消费实机 smoke 已通过：已知网络确认 1 次 -> 标题 TAP 3 次 -> Loading 观察 -> 正向 `CommonHomeReady` -> `CommonRecoveryRecovered` -> 独立 `CommonLiveHomeComplete`。普通强化 `Start` 及 `SoleilSpendPermit` 全部禁用，正向首页即停；重启 0 次、消费尝试 0 次，日志 `debug/common_recovery_live.log` 退出 0。`debug/common_recovery_network_home_verified.png` 为 17:11:02 本次生成并确认内容的首页截图。期间包含 35 秒的移动等待回合，不宣称瞬时恢复。

该实测验证的是已知网络弹窗至首页的恢复路径，不是从业务卡死诱发 30 秒冻结后自动重启，也没有进入强化或依頼；独立终点不能当成 Soleil 业务恢复完成。它也不证明此前两次未确认消费请求的服务端结果。

第二次实机 smoke 直接进入受控重启链，并将该测试的重启预算限定为 1：`CommonRecoveryRestartPermit` -> 重启前截图 -> `CommonStopGame` -> `CommonStartGame` -> 标题 TAP 3 次 -> Loading 观察 -> 正向首页 -> `CommonRecoveryRecovered` -> `CommonLiveHomeComplete`。日志 `debug/common_recovery_restart_live.log` 退出 0，重启 1 次、消费尝试 0 次；17:13:26 本次截图 `debug/common_recovery_restart_home_verified.png` 已确认是首页。生产预算仍是每 Task 累计最多 2 次重启，没有因测试而改成 1 次。

该重启 smoke 验证一次精确包的 `StopApp` / `StartApp` 和后续导航，不是故意制造卡死或实机观察到 30 秒冻结后自动触发重启。冻结分流证据来自短时原生及模拟测试，不混同为此项实机结果。两次 smoke 均已停止，结束时游戏保留首页，没有执行普通升级。

目前尚无通用恢复成功后继续完成一次真实新强化及依頼的完整验收。此前两次消费尝试当时未取得启动确认并停留网络错误，不能断言服务端未受理；恢复层不直接重放这些未确认的消费请求。冻结诱发重启、长时间循环、其他弹窗、跨语言和跨分辨率仍需各自验收。
