# AIStock R1.2 — Windows 本地测试启动脚本
# 建议从仓库根目录运行，例如：
# .\scripts\dev-windows.ps1 -Mode doctor
# .\scripts\dev-windows.ps1 -Mode api
# .\scripts\dev-windows.ps1 -Mode web
# .\scripts\dev-windows.ps1 -Mode refresh -Kind us_equity -Symbol AAPL
param(
    [ValidateSet("doctor", "api", "web", "refresh", "status")]
    [string]$Mode = "doctor",
    [string]$Kind = "us_equity",
    [string]$Symbol = "AAPL"
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$ApiRoot = Join-Path $Root "apps\api"
$WebRoot = Join-Path $Root "apps\web"
$ServicesRoot = Join-Path $Root "services"

# Workspace service directories are Python top-level packages in current project.
$ServicePaths = @(Get-ChildItem -LiteralPath $ServicesRoot -Directory | ForEach-Object { $_.FullName })
$AllPaths = @($ApiRoot) + $ServicePaths
$env:PYTHONPATH = ($AllPaths -join [IO.Path]::PathSeparator)
if (-not $env:MARKET_DATA_MODE) { $env:MARKET_DATA_MODE = "real" }

if ($Mode -eq "web") {
    Set-Location $WebRoot
    npm run dev
    exit $LASTEXITCODE
}
Set-Location $ApiRoot
$PythonExe = Join-Path $ApiRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) { $PythonExe = "python" }
if ($Mode -eq "api") {
    & $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    exit $LASTEXITCODE
}
if ($Mode -eq "doctor") {
    & $PythonExe -m app.cli.market_data doctor
} elseif ($Mode -eq "status") {
    python -m app.cli.market_data status --kind $Kind --symbol $Symbol
} elseif ($Mode -eq "refresh") {
    Write-Host "仅采集公开行情，不访问证券/期货/OKX 私人账户，也不生成交易指令。"
    python -m app.cli.market_data refresh --kind $Kind --symbol $Symbol
}
exit $LASTEXITCODE
