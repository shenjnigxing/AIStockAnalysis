# Run once after pulling branch. Installs only declared project dependencies.
# PowerShell: .\scripts\setup-windows.ps1
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "找不到 Python。请先安装 Python 3.11+ 并加入 PATH。"
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "找不到 npm。请先安装 Node.js 20+。"
}
Write-Host "Prepare isolated Python virtual environment"
$VenvRoot = Join-Path $Root "apps\api\.venv"
$PythonExe = Join-Path $VenvRoot "Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    python -m venv $VenvRoot
    if ($LASTEXITCODE -ne 0) { throw "创建 Python 虚拟环境失败" }
}
Write-Host "Install Python API dependencies"
& $PythonExe -m pip install -r (Join-Path $Root "apps\api\requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python dependencies installation failed" }

Write-Host "Install frontend dependencies"
Push-Location (Join-Path $Root "apps\web")
try {
    npm ci
    if ($LASTEXITCODE -ne 0) { throw "Web npm ci failed" }
} finally {
    Pop-Location
}
Write-Host "Local health diagnosis"
& (Join-Path $Root "scripts\dev-windows.ps1") -Mode doctor
if ($LASTEXITCODE -ne 0) { throw "Doctor check failed" }
Write-Host "完成。打开两个独立 PowerShell 终端启动 API 与 Web，操作见 docs/architecture/r12/03-evening-smoke.md"
