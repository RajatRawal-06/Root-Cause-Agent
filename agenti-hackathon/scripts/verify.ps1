$ErrorActionPreference = "Stop"

Write-Host "Running unit and API tests..."
python -m unittest discover -s tests

Write-Host "Starting local server smoke test..."
$env:PORT = "8010"
$verifyData = Join-Path (Get-Location) ".test-data"
New-Item -ItemType Directory -Force -Path $verifyData | Out-Null
$env:INCIDENT_DB_PATH = Join-Path $verifyData "incident-rca-verify.db"
$process = Start-Process -FilePath python -ArgumentList @("backend\server.py") -WindowStyle Hidden -PassThru -WorkingDirectory (Get-Location)
try {
  Start-Sleep -Seconds 2
  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8010/api/health"
  if ($health.status -ne "ok") {
    throw "Health check failed"
  }
  Write-Host "Verification passed."
}
finally {
  Stop-Process -Id $process.Id -ErrorAction SilentlyContinue
}
