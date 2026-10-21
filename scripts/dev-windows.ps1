param(
  [ValidateSet('doctor','api','web','refresh','status')][string]$Mode = 'doctor',
  [string]$Kind = 'us_equity',
  [string]$Symbol = 'AAPL'
)
. (Join-Path $PSScriptRoot '../infra/scripts/local_common.ps1')
Set-LocalEnvironment
Assert-LocalPython
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
if ($Mode -in @('api','web')) {
  & (Join-Path $RepoRoot 'infra/scripts/start_local.ps1') -Service $Mode
} elseif ($Mode -eq 'doctor') {
  & $Python -m app.cli.market_data doctor
} else {
  & $Python -m app.cli.market_data $Mode --kind $Kind --symbol $Symbol
}
exit $LASTEXITCODE
