param([switch]$RunTests)
. (Join-Path $PSScriptRoot 'local_common.ps1')
Push-Location $RepoRoot
try {
  if (-not (Test-Path $Python)) {
    # Prefer the PATH interpreter (including setup-python), never py -3's newest runtime.
    $candidates = @(
      @{ Command = 'python'; Prefix = @() },
      @{ Command = 'py'; Prefix = @('-3.12') },
      @{ Command = 'py'; Prefix = @('-3.11') }
    )
    $created = $false
    foreach ($candidate in $candidates) {
      if (-not (Get-Command $candidate.Command -ErrorAction SilentlyContinue)) { continue }
      $prefix = $candidate.Prefix
      & $candidate.Command @prefix -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)"
      if ($LASTEXITCODE -ne 0) { continue }
      & $candidate.Command @prefix -m venv .venv
      if ($LASTEXITCODE -ne 0) { throw 'Virtual environment creation failed.' }
      $created = $true
      break
    }
    if (-not $created) { throw 'Install Python 3.11 or 3.12; this dependency set does not support Python 3.14.' }
  }
  & $Python -c "import sys; sys.exit(0 if sys.version_info[:2] in ((3,11),(3,12)) else 1)"
  if ($LASTEXITCODE -ne 0) { throw 'Existing .venv uses an unsupported Python. Rename it and rerun with Python 3.11/3.12.' }
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
