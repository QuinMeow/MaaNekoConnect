# 公共首页与 Soleil 导航

## 模块边界

[navigation.json](../../../assets/resource/pipeline/navigation.json) 只负责首页与 Soleil 咖啡店总界面的共享导航。Soleil 不是家具强化页：咖啡店左上为“店舗”，家具强化页为“強化”并带“家具”分类。强化配置、选择、消费、计时及依頼调用不放进公共导航。

| 公共节点 | 契约 |
| --- | --- |
| `NavHome_Ready` | 纯识别：首页 Soleil 标签、已加载建筑和亮度均满足；不执行点击 |
| `NavSoleil_Ready` | 纯识别：咖啡店标题、右侧强化图标和亮度均满足；不代表已经进入强化 |
| `NavFooter_Home` / `NavFooter_Back` | 纯识别：对应底部按钮模板与亮度；不是任意页面的点击许可 |
| `NavHome_Ensure` | 已在正向首页则确认到达；否则仅从已知咖啡店或家具强化页点击已识别的 home |
| `NavSoleil_Ensure` | 已在正向咖啡店则确认到达；否则仅从已知首页点击 Soleil 建筑 |
| `NavHome_Arrived` / `NavSoleil_Arrived` | 再次正向确认目的页后，返回调用方锚点；点击成功不等于到达 |

首页判定沿用既有两份 UI 模板，并增加亮度门禁；不会只因 Soleil 文字仍可见就点击尚未加载好的建筑。咖啡店门禁不再只看“店舗”标题，而同时要求强化入口及明亮状态。当前亮度参数针对已有截图，不能证明所有遮罩或所有主题均已覆盖。

`NavHome_FromFurnitureEnhance` 只复用 `FurnitureEnhance_PageGuard` 的纯页面识别，再与独立 home 按钮门禁组合；不调用家具业务。公共导航不执行普通强化、付费加速、依頼、Android Back、任意关闭或未知坐标兜底。

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

导航不写入或清除 `CommonRecoveryResume`，不重置业务消费与恢复计数。网络中断或页面超时交给[通用恢复](common_recovery.md)，恢复后回调用方安全入口重新判页，不直接跳入消费动作。缺少锚点不是成功到达业务终点，应由调用方测试和结果审计发现。

## 失败与卡死

两个 Ensure 先检查已知网络中断和 Loading，再检查已到达或可执行的来源分支。点击后只等正向目的页，不通过递归调用 Ensure 盲目重点击。无法识别源页、按钮不存在、页面变暗或等待超时都不会猜点，转入有界通用恢复。

首页点击 Soleil 后无法离开首页，`NavSoleil_FromHome.on_error` 特别进入 `CommonRecoveryHomeStallEnter`。这样不会因为首页模板仍命中就误判健康并无限重试。返回首页失败则走 `CommonRecoveryEnter`，由它观察当前实际页面，不直接循环 home 点击。

Ensure 的首次分支扫描超时为 30 秒，点击后的目的页扫描为 60 秒。MaaFramework 的 `timeout` 限制当前节点扫描 `next`，不是独立等待自身识别。已经在目标页的静态画面可以正常返回；`Ready` 只证明当前画面，不证明游戏对下一次点击一定有响应。已确认首页操作无响应的调用方应使用 HomeStall 恢复，而非反复把 Ensure 当作健康测试。

## 按钮位置与业务调用

2026-10-19 已有 720 x 1280 截图中，home 按钮在底部中央，导航点击 `[345,1220,30,20]`；首页 Soleil 建筑点击 `[590,1180,20,20]`。底部 back 按钮约在 x=104..199、y=1208..1263，箭头中心约为 `(150,1228)`；若家具业务返回咖啡店，可在业务页面门禁和 `NavFooter_Back` 同时满足后使用 `[140,1220,20,20]` 等按钮内目标，并确认咖啡店到达。`[45,1220,25,20]` 位于该实拍按钮左侧，不适用。

`NavFooter_Back` 本身没有动作，公共导航也不替家具业务执行返回或依頼。不要把可见的 back 当作无条件通用关闭。`And` 识别的默认返回框也不一定是预期按钮：例如 `NavSoleil_Ready` 首先命中的是标题。调用方打开强化时必须明确强化图标的点击目标，不能使用该复合门禁的隐式 `Self` 框点击。

## 验证与限制

[导航测试](../../../tests/test_navigation.py) 先以缺少导航文件的失败用例建立契约，再验证结构与真实 MaaFramework 的页面识别。原生识别测试拒绝所有输入，隔离真实 ADB、网络和进程，不执行页面点击。截图只裁取 UI，来源、区域和合成负例见[夹具说明](../../../tests/fixtures/navigation/README.md)。

覆盖包括首页旧正例及后续独立截图、咖啡店与强化页区分、加载过场、0.5/0.75 倍变暗、关键区域移除、仅有 footer、缺少 home 按钮和黑灰白均匀画面。home/back 新模板裁自同一张既有咖啡店截图，不是独立泛化验证。

当前新导航的真实点击与到达仍需零消费 smoke 单独验收；原有网络恢复到首页的实机成功不能替代重构后的公共导航验收。未证明任意业务页返回、任意弹窗关闭、所有 dim 程度、其他分辨率或语言。`soleil_room.png`、`soleil_room_return.png` 实际为加载过场，不是咖啡店到达成功证据。
