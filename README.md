# MaaNekoConnect

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的ネココネ自动化项目。

当前包含框架连通性测试和实验性的家具单轮补位强化、间隔调度。

框架连通性测试：

1. 精确连接 `127.0.0.1:5557`，不会回退到 `127.0.0.1:5555`。
2. 通过 JSON Pipeline 启动包 `jp.goodsmile.nekoconne`。
3. 等待 20 秒。
4. 通过 MaaFramework 截图到 `debug/screencap/nekoconne_launch.png`。

家具强化通过 JSON 为列表前五格的空闲候选补位，一轮最多尝试 5 次，轮末集中点击店铺“依頼”一次。默认单轮、保留现有排序、开启依頼；另支持固定间隔及可见忙碌家具的最短/最长剩余时间调度，读取失败回退固定间隔。公共[首页/Soleil 导航](docs/zh_cn/develop/navigation.md)、筛选、强化、店铺动作、调度与计时已分模块。会消耗强化券，不使用付费加速；异常进入有预算的[通用恢复](docs/zh_cn/develop/common_recovery.md)。使用和配置见[家具强化说明](docs/zh_cn/develop/soleil_upgrade.md)。

重构前已授权实测 5 次强化启动确认，但当时仍为逐件依頼；本次单轮/轮末请求与动态调度使用离线模拟和原生视觉/OCR 验证，未新增实机消费或长时运行验收。历史网络恢复及重启回首页成功不等于现场冻结诱发重启已验证。

## 开发方式

优先使用 `assets/resource/pipeline/*.json` 和 MaaFramework 现有 API。只有 JSON 无法表达的逻辑才放到 `agent/extensions.py`。

当前 Agent 运行时固定为 Windows x64、Python 3.11.17、MaaFw 5.14.3；MFAAvalonia 打包目标固定为 v2.16.2。上游提交与校验信息见 [框架更新记录](docs/zh_cn/develop/maa_framework_updates.md)。

当前仓库独立使用，不依赖外层计划仓库、全局 Python、Conda 或 Python 的 `PATH` 配置。Windows x64 首次在仓库根目录运行：

```powershell
.\scripts\setup_python.ps1
```

脚本下载并校验锁定的 Astral Python Build Standalone 和依赖，准备项目私有的 `.runtime/python/python.exe`。源接口供 LocalBridge/MFAA 使用 `../.runtime/python/python.exe`；发布包携带同一运行时，改为 `./.runtime/python/python.exe`。应用依赖锁只含 MaaFw、numpy、MaaAgentBinary、StrEnum，不含 pytest。准备方式、完整性检查和独立测试环境见 [便携 Python 说明](docs/zh_cn/portable_python.md)。

只有已获准操作目标设备时，才运行启动截图验证，并提供实际 ADB 路径：

```powershell
.\scripts\test_nekoconne.ps1 -AdbPath '<实际 adb.exe 的绝对路径>'
```

该脚本默认使用项目私有 Python，缺失即报错，不自动回退；已有 Conda 环境仅可显式通过 `-CondaEnv` 选择。pytest/Schema 等开发工具使用另行准备的测试环境，不安装进已校验的生产运行时。2026-10-19 已完成本机 LocalBridge 默认 Agent 初始化及搬迁后发布包 Agent IPC 检查，未运行游戏任务；跨机器 GUI 和实机验收仍需单独进行，详见便携 Python 说明的验证记录。

请遵守游戏服务条款，并仅在自己的账号和设备上使用。
