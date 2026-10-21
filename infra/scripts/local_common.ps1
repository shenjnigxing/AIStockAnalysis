$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$Python = Join-Path $RepoRoot '.venv/Scripts/python.exe'
function Set-LocalEnvironment {
  $envFile = Join-Path $RepoRoot '.env'
  if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile) {
      if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
        $key = $Matches[1]; $value = $Matches[2].Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
          $value = $value.Substring(1, $value.Length - 2)
        }
        if (-not (Test-Path "Env:$key")) { Set-Item "Env:$key" $value }
      }
    }
  }
  $modulePaths = @((Join-Path $RepoRoot 'apps/api'))
  $modulePaths += @(Get-ChildItem (Join-Path $RepoRoot 'services') -Directory | ForEach-Object { $_.FullName })
  $env:PYTHONPATH = $modulePaths -join [IO.Path]::PathSeparator
  if (-not $env:API_BASE_URL -or $env:API_BASE_URL -eq 'http://api:8000') { $env:API_BASE_URL = 'http://127.0.0.1:8000' }
}
function Assert-LocalPython {
  if (-not (Test-Path $Python)) { throw 'Run infra/scripts/dev_bootstrap.ps1 first to create .venv.' }
}
