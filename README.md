# MaaNekoConnect

基于 [MaaFramework](https://github.com/MaaXYZ/MaaFramework) 的ネココネ自动化项目。

当前只实现一个框架连通性测试：

1. 精确连接 `127.0.0.1:5557`，不会回退到 `127.0.0.1:5555`。
2. 通过 JSON Pipeline 启动包 `jp.goodsmile.nekoconne`。
3. 等待 20 秒。
4. 通过 MaaFramework 截图到 `debug/screencap/nekoconne_launch.png`。

## 开发方式

优先使用 `assets/resource/pipeline/*.json` 和 MaaFramework 现有 API。只有 JSON 无法表达的逻辑才放到 `agent/extensions.py`。

环境由外层私有工作区 `MaaNekoConnect_Codex` 的脚本统一配置。配置完成后可运行：

```powershell
.\scripts\test_nekoconne.ps1
```

静态测试：

```powershell
conda run -n maanekoconnect python -m pytest -q
```

请遵守游戏服务条款，并仅在自己的账号和设备上使用。
