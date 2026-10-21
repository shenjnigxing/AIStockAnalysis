# Compatibility entry point. The shared bootstrap owns the root .venv.
& (Join-Path $PSScriptRoot '../infra/scripts/dev_bootstrap.ps1')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& (Join-Path $PSScriptRoot 'dev-windows.ps1') -Mode doctor
exit $LASTEXITCODE
