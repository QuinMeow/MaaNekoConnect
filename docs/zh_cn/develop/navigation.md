# 公共首页与 Soleil 导航

## 模块边界

[navigation.json](../../../assets/resource/pipeline/navigation.json) 负责已知页面归首页，以及首页到 Soleil 咖啡店总界面的共享导航。Soleil 不是家具强化页：咖啡店左上为“店舗”，家具强化页为“強化”并带“家具”分类。强化配置、选择、消费、计时及依頼调用不放进公共导航。

| 公共节点 | 契约 |
| --- | --- |
| `NavHome_Ready` | 纯识别：首页 Soleil 标签、已加载建筑和亮度均满足；不执行点击 |
| `NavSoleil_Ready` | 纯识别：咖啡店标题、右侧强化图标和亮度均满足；不代表已经进入强化 |
| `NavFooter_Home` / `NavFooter_Back` | 纯识别：对应底部按钮模板与亮度；不是任意页面的点击许可 |
| `NavHome_Ensure` | 绑定本次返回点后，通过共享 Normalize 清理已知弹窗、由已知业务页返回并确认首页 |
| `NavHome_Normalize` | 纯导航分流，使用私有 `NavHome_NormalizeReturn`；不执行页面原有的业务后继 |
| `NavHome_AwaitHome` | Home 点击后的等待；接受首页、加载、异常和弹窗，不再次点击原业务页 |
| `NavSoleil_Ensure` | 已在正向咖啡店则确认到达；否则先归首页再点击 Soleil 建筑 |
| `NavHome_Arrived` / `NavSoleil_Arrived` | 再次正向确认目的页后，返回调用方锚点；点击成功不等于到达 |

首页判定沿用既有两份 UI 模板，并增加亮度门禁；不会只因 Soleil 文字仍可见就点击尚未加载好的建筑。咖啡店门禁不再只看“店舗”标题，而同时要求强化入口及明亮状态。当前亮度参数针对已有截图，不能证明所有遮罩或所有主题均已覆盖。

`NavHome_FromFurnitureEnhance` 只复用 `FurnitureEnhance_PageGuard` 的纯页面识别，再与独立 home 按钮门禁组合；不调用家具业务。公共导航不执行普通强化、付费加速、依頼、Android Back 或无条件坐标盲点。

2026-10-20 串行调试增加 Quest、地图、VR、比赛、交换、礼物、备战、卡池、社团及成员页的纯识别，再与 `NavFooter_Home` 同时确认。菜单、好友、每日列表、邮箱、容量不足、社团帮助/赞助及普通奖励只关闭，不调用业务模块的领取、帮助或消费节点。首页按钮每 Task 共享最多八次，正常静态业务页不会仅因静止而重启。

## 登录提示清理

2026-10-19 跨日探索后，两个 Ensure、home 返回后的目的页等待、Soleil 点击后的等待均先处理登录失败退出/游玩设备确认/访问拒绝/跨日/网络/Loading 等特殊情况，再按通用控件清理提示，最后确认目的页。实测、关闭位置与每日清单见[观测记录](daily_observation_20261019.md)，随后手机登录触发的设备冲突见[每日任务探索](daily_tasks_research.md)。按用户要求，不再为每种登录奖励或活动增加模板。

「ゲームサーバへのアクセスが拒否されました。」须与「タイトルへ」共同命中；「プレイ端末の確認」须同时命中专用标题、正文和 OK。两者均交给[通用恢复](common_recovery.md)，不能点击画面下方仍可见的 Close。网络、跨日、访问拒绝、设备确认、登录失败的确认上限依次为每 Task 3/3/3/1/1 次，返回首页或恢复 Dispatch 不清零。专用无计数 Gate 先识别错误，再转有限额 Confirm 或截图停止；不能依赖耗尽后会被框架跳过的 Confirm 来阻挡通用关闭，因此重复设备确认或登录失败不会演变成反复抢登或点穿弹窗。

2026-10-20 11:06:24 的 `debug/on_error/2026.10.20-11.06.24.427_Daily_FriendMenu.png` 显示「ログインに失敗しました」及「サーバーへの接続に失敗しました / ゲームを終了します」。这是独立的退出型登录失败，不是原“返回标题”网络错误。`CommonLoginFailedInterrupt` 在导航判页列表中均先于通用 Close；进入公共恢复后，专用标题、退出正文及复用的 `CommonPlayDeviceButton` 同时命中才点一次 OK，再使用原共享 `CommonRecoveryRestartPermit`，本 Task 累计最多两次重启。没有新 Task、预算清零、底层 Close 回退或业务重放。新增分支已有离线回归，修复后尚未实机验收。

依次尝试：明亮的通用圆形 Close；「画面をタップして続ける」提示；通用奖励外框。Close 不要求公告标题/标签，继续提示不要求复选框说明；奖励页只检查不含文字的左侧橙色飘带、下方面板及底部空白，不读取活动名称、奖励内容或「受取」，已移除月度/活动/半周年专用模板。后两种情况点已验证的底部空白。沿用这些 UI 的新活动不需要新增素材；布局或按钮样式整体改变仍需验证。

Close、继续提示及奖励面板有亮度/颜色门禁，拒绝本次 0.75 倍变暗负例，不承诺覆盖所有遮罩强度。不得点击活动、卡池、右上商店或复选框，也不对没有通用控件/外框的任意画面盲点。每次点击后重新判页。`NavHome_PopupPermit.max_hit=20` 是整个 Task 共用预算，包含没有离页的尝试；恢复不清零，耗尽截图并停止。

导航自行绑定 `NavHome_PopupReturn` 返回自身安全入口；公共恢复把它绑定到 `CommonRecoveryDispatch`，避免误用业务的 `NavHome_Return`。`NavHome_PopupAction` 在识别提示后绑定，取得许可后点击前再次检查页面。均不改调用方的消费、调度和恢复锚点。

## 返回锚点

调用方在安全入口绑定 `NavHome_Return`、`NavSoleil_Return` 以及自己的 `CommonRecoveryResume`，例如：

```json
{
  "ExampleEntry": {
    "recognition": "DirectHit",
    "anchor": {
      "NavHome_Return": "ExampleAfterHome",
      "NavSoleil_Return": "ExampleAfterSoleil",
      "CommonRecoveryResume": "ExampleEntry"
    },
    "next": ["NavHome_Ensure"]
  },
  "ExampleAfterHome": {
    "recognition": "DirectHit",
    "next": ["NavSoleil_Ensure"]
  },
  "ExampleAfterSoleil": {
    "recognition": "DirectHit",
    "next": []
  }
}
```

这是接入示意，不是执行授权。`NavHome_Arrived` 跳转 `[Anchor]NavHome_Return`，`NavSoleil_Arrived` 跳转 `[Anchor]NavSoleil_Return`。锚点由 Task 上下文保存，不是自动调用栈；有多种调用位置时应在调用前重新绑定，避免沿用旧返回点。

`NavHome_Ensure` 私有返回点指向 `NavHome_Arrived`，`NavSoleil_Ensure` 指向 `NavSoleil_FromHome`，日常收尾 `Daily_Return` 则指向 `Daily_OnHome`。三者每次调用均重绑 `NavHome_NormalizeReturn`，不把入口业务的 `NavHome_Return` 用作收尾。旧 `NavHome_FromSoleil` / `NavHome_FromFurnitureEnhance` 兼容入口也自行绑定该私有点，旧 caller 无需新增配置。

导航不写入或清除 `CommonRecoveryResume`，不重置业务消费与恢复计数。网络中断或页面超时交给[通用恢复](common_recovery.md)，恢复后回调用方安全入口重新判页，不直接跳入消费动作。缺少锚点不是成功到达业务终点，应由调用方测试和结果审计发现。

## 失败与卡死

两个 Ensure 先检查登录失败退出、设备确认、访问拒绝、日期变化、已知网络中断和 Loading，再检查通用提示、已到达或可执行的来源分支。点击后只等正向目的页，不通过递归调用 Ensure 盲目重点击。归首页时无法识别源页、按钮不存在、页面变暗或等待超时均截图停止，不猜点、不为普通静态页启动重启链。

首页点击 Soleil 后无法离开首页，`NavSoleil_FromHome.on_error` 特别进入 `CommonRecoveryHomeStallEnter`。这样不会因为首页模板仍命中就误判健康并无限重试。归首页期间明确的异常交公共恢复；Home 点击无效则在 `NavHome_AwaitHome` 等待后停止，不直接循环 Home 点击。

Normalize 首次分支和 Home 点击后等待均为 30 秒，首页点击 Soleil 后的目的页扫描为 60 秒。MaaFramework 的 `timeout` 限制当前节点扫描 `next`，不是独立等待自身识别。已经在目标页的静态画面可以正常返回；`Ready` 只证明当前画面，不证明游戏对下一次点击一定有响应。已确认首页操作无响应的调用方应使用 HomeStall 恢复，而非反复把 Ensure 当作健康测试。

## 按钮位置与业务调用

2026-10-19 已有 720 x 1280 截图中，home 按钮在底部中央，导航点击 `[345,1220,30,20]`；首页 Soleil 建筑点击 `[590,1180,20,20]`。底部 back 按钮约在 x=104..199、y=1208..1263，箭头中心约为 `(150,1228)`；若家具业务返回咖啡店，可在业务页面门禁和 `NavFooter_Back` 同时满足后使用 `[140,1220,20,20]` 等按钮内目标，并确认咖啡店到达。`[45,1220,25,20]` 位于该实拍按钮左侧，不适用。

`NavFooter_Back` 本身没有动作，公共导航也不替家具业务执行返回或依頼。不要把可见的 back 当作无条件通用关闭。`And` 识别的默认返回框也不一定是预期按钮：例如 `NavSoleil_Ready` 首先命中的是标题。调用方打开强化时必须明确强化图标的点击目标，不能使用该复合门禁的隐式 `Self` 框点击。

## 验证与限制

[导航测试](../../../tests/test_navigation.py) 先以缺少导航文件的失败用例建立契约，再验证真实 MaaFramework 的页面识别及模拟控制器页面迁移。它隔离真实 ADB、网络和进程，点击仅驱动离线夹具，不操作设备。截图只裁取 UI，来源、区域和合成负例见[夹具说明](../../../tests/fixtures/navigation/README.md)。

覆盖包括首页旧正例及后续独立截图、咖啡店与强化页区分、加载过场、0.5/0.75 倍变暗、关键区域移除、仅有 footer、缺少 home 按钮和黑灰白均匀画面。home/back 新模板裁自同一张既有咖啡店截图，不是独立泛化验证。

五类错误另有底层 Close 可见的优先级回归；[恢复模块测试](../../../tests/test_recovery.py) 覆盖次数耗尽后立即停止、访问拒绝接续设备确认、登录失败确认后共享重启及安全返回，不重放强化或其他消费动作。新增 UI-only 素材来自 `daily_20261019_41_after_phone_home.png`、`daily_20261019_43_denied_title_ready.png` 和上述 `11.06.24.427_Daily_FriendMenu` 故障截图，裁剪坐标与保留内容见[恢复夹具说明](../../../tests/fixtures/recovery/README.md)。这些是实际截图上的离线识别与模拟点击，不是设备端自动导航验收。

2026-10-19 23 点后已手动实测主页进入 Soleil、确认加载完成及 home 返回；这是画面与坐标观测，不是自动 JSON 导航验收。上一轮准备自动 smoke 时发现用户正在操作，按要求停止实机点击；随后用户明确停止手机操作并授权继续探索，新增访问拒绝和设备确认观测。手动处理与原有网络恢复成功均不能替代真实公告自动关闭、自动往返及新增异常链的自动验收。未证明任意业务页返回、任意弹窗关闭、所有 dim 程度、其他分辨率或语言。`soleil_room.png`、`soleil_room_return.png` 实际为加载过场，不是咖啡店到达成功证据。

2026-10-20 新增浏览器 MPE 正反序五项串行验证及社团残留页→首页、好友/菜单两层关闭的实际节点轨迹，证据与业务未确认的保留说明见[每日串行记录](daily_automation.md#串行衔接修复与-mpe-验证)。十二入口与家具入口的跨 Task 顺序覆盖仍以原生离线模拟为主，不宣称所有排列或未知页面均已实机通过。
