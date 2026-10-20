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
| 家具单轮强化 | `test_furniture_round.py` |
| Soleil 店铺依頼 | `test_soleil_shop.py` |
| 家具调度 | `test_furniture_schedule.py` |
| 家具计时扩展与识别 | `test_furniture_timer.py` |
| 通用恢复扩展与流程 | `test_recovery.py` |
| CLI 与编辑器选项映射 | `test_soleil_options.py` |
| 强化运行入口与结果审计 | `test_run_soleil_upgrade.py` |

## 验证边界

测试默认禁止真实进程启动、网络连接和设备输入。原生识别用例只识别裁剪 UI；流程用例在模拟控制器上执行真实 Pipeline 分流，必要时替换识别结果、计时或业务动作。它们不是当前账号、游戏版本或实机操作的验收。

编辑器选项测试按 MFAA 的有序 override 数组调用原生 `post_task`，验证固定/最短/最长模式与 90 秒输入。节点字段覆盖不递归合并 `custom_action_param`；局部参数丢失 `op` 的旧故障保留为拒绝执行回归。

从仓库根目录运行 `python -m pytest -q`；完整离线验证命令见 [AGENTS.md](../AGENTS.md)。2026-10-19 精简前的 658 项回归全部通过；精简后以当前用例为准，不再维护旧版逐字段测试和完整矩阵。
