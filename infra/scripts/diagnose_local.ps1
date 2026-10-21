. (Join-Path $PSScriptRoot 'local_common.ps1')
Set-LocalEnvironment
Assert-LocalPython
Push-Location $RepoRoot
try {
  & $Python -c "import sys; from zoneinfo import ZoneInfo; from app.main import app; from app.db.init_db import init_db; init_db(); print('Python:', sys.version.split()[0]); print('Timezone:', ZoneInfo('Asia/Shanghai')); print('API import and database: OK')"
  if ($LASTEXITCODE -ne 0) { throw 'Python, timezone, API import or database check failed.' }
  & node --version
  if ($LASTEXITCODE -ne 0) { throw 'Node.js is unavailable.' }
  foreach ($url in @('http://127.0.0.1:8000/health', 'http://localhost:3000/api/research/v3/market-data/sources')) {
    try {
      $null = Invoke-RestMethod -Uri $url -TimeoutSec 10
      Write-Host "$url OK"
    } catch { throw "$url unavailable. Start the API/Web consoles and inspect their logs." }
  }
} finally { Pop-Location }
