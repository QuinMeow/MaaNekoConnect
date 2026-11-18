param([string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot))

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $ProjectRoot).Path
$lock = Get-Content -LiteralPath (Join-Path $root 'tools/python-runtime.lock.json') -Raw | ConvertFrom-Json
if ($lock.schema_version -ne 1 -or $lock.target -ne 'win-x64' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Portable Python currently supports Windows x64 only.'
}
$runtime = Join-Path $root '.runtime'
New-Item -ItemType Directory -Path $runtime -Force | Out-Null
if ((Get-Item -LiteralPath $runtime).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'The project runtime directory must not be a symbolic link or junction.'
}
$cache = Join-Path $runtime 'cache'
New-Item -ItemType Directory -Path $cache -Force | Out-Null
if ((Get-Item -LiteralPath $cache).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'The runtime cache must not be a symbolic link or junction.'
}
$archive = Join-Path $cache 'cpython-win-x64.tar.gz'
if (-not (Test-Path -LiteralPath $archive) -or (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $lock.python.sha256) {
    if (-not $lock.python.url.StartsWith('https://github.com/astral-sh/python-build-standalone/releases/download/')) {
        throw 'Untrusted Python distribution URL.'
    }
    Invoke-WebRequest -UseBasicParsing -Uri $lock.python.url -OutFile $archive
}
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $lock.python.sha256) {
    throw 'Python distribution SHA256 mismatch.'
}
# Never execute an existing runtime before its integrity has been checked.
$bootstrap = Join-Path $runtime ('bootstrap-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $bootstrap | Out-Null
try {
    & (Join-Path $env:WINDIR 'System32/tar.exe') -xf $archive -C $bootstrap
    if ($LASTEXITCODE -ne 0) { throw 'Could not extract the Python bootstrap.' }
    $python = Join-Path $bootstrap 'python/python.exe'
    # Build-time bootstrap only; the Agent always uses the validated .runtime/python.
    & $python -E -s (Join-Path $root 'tools/prepare_python.py') --project-root $root --target win-x64
    if ($LASTEXITCODE -ne 0) { throw 'Portable Python setup failed.' }
} finally {
    $cleanup = (Resolve-Path -LiteralPath $bootstrap).Path
    if ((Split-Path -Parent $cleanup) -ne $runtime -or
        (Split-Path -Leaf $cleanup) -notmatch '^bootstrap-[0-9a-f]{32}$' -or
        (Get-Item -LiteralPath $cleanup).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Refusing cleanup outside the generated project bootstrap directory.'
    }
    Remove-Item -LiteralPath $cleanup -Recurse -Force
}
