# 每日任务文档素材

## 来源与处理边界

本目录仅保存每日任务人工研究所需的 UI 裁片，不是自动识别模板，也不证明对应动作已经执行。原图为本机已忽略的 `debug/screencap/daily_20261019_*.png`，720 x 1280、日文界面、游戏 2.2.0、JP2；本轮时段与完成边界见[研究正文](../../daily_tasks_research.md)。文件名前缀是会话标识，不代表每张原图都摄于北京时间 2026-10-19。

使用 Pillow 从原图原尺寸无损裁剪，未缩放、重绘、修补或调整颜色；不把多张截图拼接成一张证据。裁剪框采用 Pillow 的 `(left, top, right, bottom)`，坐标原点为原图左上，右边界、下边界不包含在内。完整原图未入库，下表以文件名而非指向忽略目录的 Markdown 链接记录来源。

裁剪排除了玩家姓名、好友头像、完整角色和账号余额。奖励面板中的数字是本次所得或任务奖励，不是账号持有余额；免费剩余次数、商品价格、库存和任务进度作为必要控件信息保留。局部地图/场景背景仅用于辨认对应入口。

## 素材索引

| 裁片 | 原图 | 裁剪框 | 用途与解释边界 |
| --- | --- | --- | --- |
| [daily_completed_rows.png](daily_completed_rows.png) | `daily_20261019_95_daily_sales_final.png` | `(67, 318, 654, 923)` | 营业收入、问候、配送三项均 `1/1`，各行仍有「受け取り」；达标不等于每日奖励已领取。只保留任务列表，不含背景角色。 |
| [daily_batch_reward.png](daily_batch_reward.png) | `daily_20261019_49_claim_login.png` | `(108, 487, 482, 603)` | 一次点击后的合并奖励：`9000` 金币、`30 DayPt`、`30 PassPt`；不是余额，也不是额外完成三次任务。 |
| [exchange_friend_coin_offer.png](exchange_friend_coin_offer.png) | `daily_20261019_54_exchange_community.png` | `(37, 375, 350, 558)` | 好友币 `10` 换 `1000000` 金币的商品、价格和交换按钮。本轮只查看，未交换；不能视为免费或自动消费许可。 |
| [friend_greeting_control.png](friend_greeting_control.png) | `daily_20261019_59_friend_greeting.png` | `(500, 303, 640, 354)` | 单人「挨拶」按钮；不含该好友姓名、头像、评价或账号余额。它不是一键问候按钮。 |
| [surrounding_map_entry.png](surrounding_map_entry.png) | `daily_20261019_69_delivery_loaded.png` | `(17, 867, 163, 1008)` | Soleil 的「周辺マップ」入口；区别于商品开发/陈列和车库场景。 |
| [delivery_complete_pin.png](delivery_complete_pin.png) | `daily_20261019_74_surrounding_map.png` | `(8, 596, 149, 755)` | 「配達完了！」pin，是本轮领取已有完成配送的入口；不是新订单派出按钮。 |
| [delivery_cost_control.png](delivery_cost_control.png) | `daily_20261019_79_delivery_auto_team.png` | `(225, 1061, 495, 1147)` | 红色「配達」按钮标价 `1000` 电池 Pt。本轮未按，不显示上方角色编队和账号电池余额。 |
| [sales_income_panel.png](sales_income_panel.png) | `daily_20261019_88_sales_notification.png` | `(65, 187, 655, 965)` | 「売上報酬獲得」普通收入面板、所得与追加入口。底部「追加で獲得する」未点击，不是普通 Close；追加规则和免费/钻石区别见正文。 |
| [sales_reward_items.png](sales_reward_items.png) | `daily_20261019_92_sales_closed.png` | `(108, 487, 613, 603)` | 关闭普通收益面板后弹出的所得项目；只留奖励条，不含背景立绘、账号余额或推断性物品名称。 |
| [vr_free_skip.png](vr_free_skip.png) | `daily_20261019_102_vr_main.png` | `(506, 1024, 668, 1124)` | 「無料 あと2回」「スキップクリア」控件；只证明此截图有两次免费额度，不证明已跳过或已计入每日条件。 |
| [vr_daily_completed.png](vr_daily_completed.png) | `daily_20261019_136_daily_vr_count.png` | `(67, 434, 653, 634)` | 本轮一次免费跳过后，VR 每日条件已 `1/1`，奖励仍可领取。该裁片本身不显示跳过余数；不能把旧的两次免费额度理解为执行后仍有两次。 |
| [contest_start_free_three.png](contest_start_free_three.png) | `daily_20261019_139_contest_prepare_once.png` | `(25, 1085, 500, 1167)` | 比赛准备页「無料挑戦：残り3回」与「開店」按钮；不含队伍、对手名或角色。是本次挑战前的次数。 |
| [contest_free_two_remaining.png](contest_free_two_remaining.png) | `daily_20261019_143_contest_remaining.png` | `(50, 741, 670, 797)` | 一次免费比赛后，免费挑战剩两次的横条；不含下方对手名。右侧另有刷新剩余三次，不代表已验证刷新免费。 |
| [gacha_video_free_single.png](gacha_video_free_single.png) | `daily_20261019_125_gacha_video.png` | `(270, 1011, 450, 1102)` | 「広告視聴で1回無料」与「1回」按钮中央区域。为排除背景人物，未保留按钮外缘；只证明广告单抽入口存在，不证明本轮已观看广告或抽卡。 |
| [daily_eight_of_nine.png](daily_eight_of_nine.png) | `daily_20261019_149_daily_eight_ready.png` | `(67, 158, 654, 730)` | 最终 `80 DayPt`、20/40/60/80 阶段礼物提示、交换 `0/1` 与汇总 `8/9`。本轮只剩交换未完成，阶段礼物未领，不能宣称每日全清。 |
| [gift_start_controls.png](gift_start_controls.png) | `daily_20261019_108_gift_preparation_ready.png` | `(220, 1085, 685, 1167)` | 礼物关卡准备页「開店」和「クイック開店」复选框；截图中快速开店未勾选，不含编队和角色，也不单凭按钮出现证明关卡已执行。 |

本机可复现脚本为已忽略的 `config/crop_daily_tasks_assets.py`，只读原图并写本目录 PNG。未经当前截图和成本复核，不应把这些固定裁剪坐标当作游戏操作坐标。

## 自动化验收补充

[daily_final_complete.png](daily_final_complete.png) 来自 `debug/daily-runs/20261019T182213Z_1792434133931193700/daily_complete.png`，对应北京时间 2026-10-20 02:22 的默认流程重复验收，裁剪框 `(67,170,654,905)`。它是同一张真实截图的连续区域，保留 100P、阶段礼物已领、汇总 9/9 与受取済み，不含账号余额或背景完整角色，未拼接、缩放或重绘。该次运行消费尝试为零；此前唯一一次自动金币兑换及验证范围见[自动化说明](../../daily_automation.md)。复现脚本为已忽略的 `config/crop_daily_acceptance.py`。

## 浏览器串行证据

### 条件启动补充

`login_cold_serial_report.json` 来自 `debug/daily-runs/20261020T053705Z_1792474625063398100/report.json`；`login_open_serial_report.json` 来自 `debug/daily-runs/20261020T054339Z_1792475019422924700/report.json`。字段原样复制，仅统一 LF，保留完整节点轨迹和 `game_completion=unverified`，不是人工改写的成功摘要。前者为进程退出后的登录→邮箱→好友，后者为已在前台的登录→好友→邮箱；均正常收尾、消费尝试为空，不证明每日条件全完成。

`login_cold_serial_home.png` 来自 2026-10-20 13:42:59 的 `debug/screencap/daily_20261019_219_login_cold_done.png`，本次真实设备原图，未裁剪/重绘，包含游戏角色和当时余额；仅作人工观测，不参与离线识别。MPE 旧控制器在本轮停止阶段超时，不能把旧 `3/3` 当作最终完整验收，见[登录启动记录](../../daily_automation.md#登录启动本轮验证)。

`mpe_serial_forward_20261020.png`、`mpe_serial_reverse_20261020.png` 为 2026-10-20 本轮浏览器 API 原样保存的 MPE 全窗口截图，来自已忽略的 `config/` 同名文件，未裁剪、拼接或重绘。保留应用上下文、固定设备地址、`5/5` 及实际首页，含游戏角色和当时资源余额，仅作人工验收证据，不参与模板识别或离线夹具。正向为登录→收入→好友→社团→邮箱，倒序相反；业务未确认和 MPE 状态解释见[串行记录](../../daily_automation.md#串行衔接修复与-mpe-验证)，不能单凭 `5/5` 声称每项日常均成功。
