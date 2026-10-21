param([ValidateSet('api','web','all')][string]$Service = 'all')
. (Join-Path $PSScriptRoot 'local_common.ps1')
Set-LocalEnvironment
Assert-LocalPython
if ($Service -eq 'all') {
  # Launch separate consoles so Ctrl+C stops each server and logs remain visible.
  $shell = (Get-Process -Id $PID).Path
  foreach ($part in @('api','web')) {
    Start-Process -FilePath $shell -ArgumentList @('-NoExit', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ('"' + $PSCommandPath + '"'), '-Service', $part)
  }
  Write-Host 'API and Web consoles launched. Open http://localhost:3000/research when ready.'
  exit
}
Push-Location $RepoRoot
try {
  if ($Service -eq 'api') { & $Python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 }
  else { & npm.cmd --prefix apps/web run dev }
  if ($LASTEXITCODE -ne 0) { throw "$Service exited with an error." }
} finally { Pop-Location }
