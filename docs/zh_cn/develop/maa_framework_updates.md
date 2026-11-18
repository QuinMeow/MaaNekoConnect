# MaaFramework 更新记录

## 2026-10-19 同步 v5.14.3

项目由 MaaFw 5.10.5 升级为 [MaaFramework v5.14.3](https://github.com/MaaXYZ/MaaFramework/releases/tag/v5.14.3)（2026-10-10 发布的稳定版）。Python 依赖、Windows 原生打包版本和 maa-tools 使用同一版本；不跟随预发布版或 main。

上游修复包括 Android 13+ 默认方向查询、Agent 超时响应匹配、Python 图像通道处理，并补全接口导入顶层 group 的 Schema。本项目当前只使用启动截图链路，现有 Python API 和 StartApp/Screencap 节点无需业务改写；新增识别、图像推理等能力没有在本项目启用。

### Schema 来源

`deps/tools/` 六份 `*.schema.json` 原样同步自固定提交 [`8963191215ca49d6b037802acd07d20a4213160a`](https://github.com/MaaXYZ/MaaFramework/tree/8963191215ca49d6b037802acd07d20a4213160a/tools)。下载后逐一核对 Git blob SHA-1，保留原始字节，包括上游文件的末尾换行状态。

| 文件 | 上游 Git blob SHA-1 |
| --- | --- |
| `custom.action.schema.json` | `6f4d79a77b4abd059fd588ae5c9d041df957191f` |
| `custom.recognition.schema.json` | `a90bcb261411ffdabd8dc43bd24a64090e39cc1d` |
| `interface.schema.json` | `f0bb3c9d1f793173108970067e4620feee2175e3` |
| `interface_config.schema.json` | `021f68fb043bc108cc9593a49b88ede77cc45be9` |
| `interface_import.schema.json` | `bfe3e9204837aa7d56450f822ca2e2cf561d82b9` |
| `pipeline.schema.json` | `20af2d353600f5ccab9731a4ac7a30aea71ec343` |

### 同步与验证约定

maa-tools 配置使用 npm 版本字符串 `5.14.3`；GitHub 发布下载使用 tag `v5.14.3`。前缀差异可在 [maa-version-manager 源码](https://github.com/neko-para/maa-support-extension/blob/39c5326d25e3db29fa597a974dbb6a3432645c14/pkgs/maa-version-manager/src/index.ts#L132) 核对。

`check.yml` 已把 `deps/tools/**` 纳入触发范围，Schema 单独变更也会触发校验。`sync_schema_files.yml` 仍保留模板仓库限制，未在本项目启用定时自动提交；下载逻辑改为读取 `requirements.txt` 的固定版本，同步全部六份文件，并在 HTTP 失败时中止。

后续升级同时更新依赖、打包工作流、maa-tools 配置、来源记录和六份 Schema，再执行 [根 AGENTS.md](../../../AGENTS.md) 中的 Schema、语法、pytest 检查及必要的实机回归。PowerShell 运行前设置 `$env:PYTHONUTF8 = "1"`，避免校验工具的 Unicode 输出被本机 GBK 编码阻断。

### 本次验证结果

- Python 3.11.17 临时隔离环境安装 MaaFw 5.14.3，原生日志确认加载 `Version v5.14.3`。
- 六份 Schema 的上游哈希、项目 Schema 校验、Python compileall、12 项 pytest 均通过。
- 三份修改的工作流可解析为 YAML；同步步骤的 Bash 语法检查通过，版本提取结果为 `v5.14.3`。
- 原有 PowerShell 入口精确连接 `127.0.0.1:5557` 并完成启动截图，耗时 27.09 秒；新 PNG 为 720×1280、1,044,073 字节，SHA-256 为 `ca710f892c82d515004989fc621e17f3956976c85af68df3b4dc64c2ebb132dd`。已查看画面，当前显示游戏首页。本轮未执行登录或业务点击，现有任务仍只是启动、等待、截图。
- 本机仍需显式指定 C 盘实际 ADB 路径和临时 Conda 环境；Conda 的 cmd AutoRun 警告未阻止本次运行，未修改注册表。未构建或发布 GUI 安装包，未提交或推送。

逐阶段命令、退出码、依赖版本、截图与日志保存在本机忽略目录 `debug/verification/upstream_v5_14_3/`。
