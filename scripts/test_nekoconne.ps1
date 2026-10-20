param(
    [string]$CondaEnv = "",
    [string]$Address = "127.0.0.1:5557",
    [string]$AdbPath = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Arguments = @(
    (Join-Path $ProjectRoot "tools\run_launch_capture.py"),
    "--project-root", $ProjectRoot,
    "--address", $Address
)
if ($AdbPath) {
    $Arguments += @("--adb-path", $AdbPath)
}

if ($CondaEnv) {
    $CondaArguments = @("run", "-n", $CondaEnv, "python") + $Arguments
    & conda @CondaArguments
} else {
    $Python = Join-Path $ProjectRoot ".runtime\python\python.exe"
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        throw "Project Python is missing: $Python. Run .\scripts\setup_python.ps1; no system Python fallback."
    }
    & $Python @Arguments
}
if ($LASTEXITCODE -ne 0) {
    throw "ネココネ启动截图测试失败，退出码：$LASTEXITCODE"
}
