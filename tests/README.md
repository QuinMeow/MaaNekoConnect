# 轻量测试约定

- 每个功能或模块最多一个 `test_*.py`；每个 Python 测试文件不超过 200 个物理行，含导入、辅助代码、注释和空行。允许多个用例和参数化边界测试。
- 测试保护行为与稳定的安全契约，不逐字段复述实现，不锁死无关文案、节点名或完整配置。精确分支顺序影响安全时可以检查顺序。
- Schema 校验负责格式；`test_project_config.py` 统一检查重复节点、资源引用和行数限制。模块归属通过下表维护，不为绕过上限拆出新模块或辅助文件。
- `conftest.py` 只提供共享夹具、加载、离线隔离和原生测试引擎，不存放业务用例；同样不超过 200 行。
- 测试源码与必要的脱敏样本纳入 Git。缓存、日志、临时截图和 OCR 模型不纳入 Git。缺 OCR 模型时只跳过原生 OCR 用例，不跳过普通单元测试。

## 模块归属

| 功能或模块 | 唯一测试文件 |
| --- | --- |
| 项目资源与测试约束 | `test_project_config.py` |
| 启动截图工具 | `test_run_launch_capture.py` |
| 打包工具 | `test_install.py` |
| 便携 Python 准备与完整性 | `test_portable_python.py` |
| 公共导航 | `test_navigation.py` |
| 家具筛选 | `test_furniture_filter.py` |
| 家具单轮强化与轮末店铺依頼 | `test_furniture_round.py` |
| 家具调度与 Interface 选项覆盖 | `test_furniture_schedule.py` |
| 家具计时扩展与识别 | `test_furniture_timer.py` |
| 通用恢复扩展与流程 | `test_recovery.py` |
| 日志内容与未知数值 | `test_runtime_logs.py` |
| Soleil 浴室目标与当番顺序 | `test_soleil_daily.py` |
| Soleil 复选项组合与家具配置保留 | `test_soleil_task.py` |
| 免费比赛、对手选择与评分刷新许可 | `test_daily_contest.py` |
| 交换所逐格购买与免费更新许可 | `test_daily_exchange.py` |
| 日常领奖与列表切换 | `test_daily_rewards.py` |
| 日常共享导航与收尾 | `test_daily_core.py` |
| 登录条件启动 | `test_daily_login.py` |
| 好友问候 | `test_daily_friend.py` |
| 邮箱领取 | `test_daily_mail.py` |
| 社团问候、帮助与赞助 | `test_daily_guild.py` |
| 配送识别与派单 | `test_delivery.py` |
| 礼物关卡选择与快速开店 | `test_daily_gift.py` |
| VR 免费次数核验 | `test_daily_vr.py` |
| 广告抽卡流程 | `test_daily_gacha.py` |
| 广告关闭扩展 | `test_ad_close.py` |

每日和家具业务 CLI 已移除，不保留其专用测试或另一套选项映射。家具 Pipeline 合并为一个 JSON 不等于把不同安全契约压进一个超长测试；筛选、单轮、调度、计时仍各自使用一个轻量测试文件。

## 验证边界

测试默认禁止真实进程启动、网络连接和设备输入。原生识别用例只识别裁剪 UI；流程用例在模拟控制器上执行真实 Pipeline 分流，必要时替换识别结果、计时或业务动作。它们不是当前账号、游戏版本或实机操作的验收。

编辑器选项测试按 MFAA 的有序 override 数组调用原生 `post_task`，验证固定/最短/最长模式与 90 秒输入。节点字段覆盖不递归合并 `custom_action_param`；局部参数丢失 `op` 的旧故障保留为拒绝执行回归。

显式选择独立 Python 3.11 测试环境后，从仓库根目录运行其 `python.exe -m pytest -q --basetemp .pytest_cache/tmp`；复用这一临时目录，不在 `config/` 下为每次测试创建目录。完整离线验证命令见 [AGENTS.md](../AGENTS.md)，不要使用生产 `.runtime/python` 安装 pytest。2026-10-19 精简前的 658 项回归全部通过；精简后以当前用例为准，不再维护旧版逐字段测试和完整矩阵。
