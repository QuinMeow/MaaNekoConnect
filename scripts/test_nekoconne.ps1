param(
    [string]$CondaEnv = "maanekoconnect",
    [string]$Address = "127.0.0.1:5557",
    [string]$AdbPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Arguments = @(
    "run", "-n", $CondaEnv, "python",
    (Join-Path $ProjectRoot "tools\run_launch_capture.py"),
    "--project-root", $ProjectRoot,
    "--address", $Address
)
if ($AdbPath) {
    $Arguments += @("--adb-path", $AdbPath)
}

& conda @Arguments
if ($LASTEXITCODE -ne 0) {
    throw "ネココネ启动截图测试失败，退出码：$LASTEXITCODE"
}
