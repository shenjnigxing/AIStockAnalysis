param(
  [switch]$RunTests
)

Write-Host "[bootstrap] installing web deps"
Push-Location "apps/web"
npm install
Pop-Location

if ($RunTests) {
  Write-Host "[bootstrap] running backend tests"
  Push-Location "apps/api"
  & 'D:\Users\sjx\Anaconda\envs\py311\python.exe' -m pytest -q
  Pop-Location
}
