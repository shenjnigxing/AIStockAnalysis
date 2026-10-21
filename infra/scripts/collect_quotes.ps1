param(
  [string]$Watchlist = (Join-Path $PSScriptRoot 'quotes-watchlist.example.json'),
  [int]$Interval = 0,
  [int]$Cycles = 1
)
. (Join-Path $PSScriptRoot 'local_common.ps1')
Set-LocalEnvironment
Assert-LocalPython
& $Python -m app.cli.quotes --watchlist $Watchlist --interval $Interval --cycles $Cycles
exit $LASTEXITCODE
