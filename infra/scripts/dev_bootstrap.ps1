param([switch]$RunTests)
. (Join-Path $PSScriptRoot 'local_common.ps1')
Push-Location $RepoRoot
try {
  if (-not (Test-Path $Python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv .venv }
    else { & python -m venv .venv }
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required.' }
  }
  & $Python -m pip install -r apps/api/requirements.txt
  if ($LASTEXITCODE -ne 0) { throw 'Backend dependency installation failed.' }
  & npm.cmd ci --prefix apps/web
  if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
  Set-LocalEnvironment
  if ($RunTests) {
    # Never run destructive test fixtures against the user's configured database.
    $savedDb = $env:DATABASE_URL
    try {
      $env:DATABASE_URL = 'sqlite:///:memory:'
      & $Python -m pytest -q apps/api/tests tests/unit
      if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed.' }
    } finally { $env:DATABASE_URL = $savedDb }
  }
  Write-Host 'Ready. Run infra/scripts/start_local.ps1, then open http://localhost:3000/research'
} finally { Pop-Location }
