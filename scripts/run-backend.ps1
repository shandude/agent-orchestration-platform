# Run the backend locally on Windows.
#   ./scripts/run-backend.ps1
# Creates a venv (if missing), installs deps, and starts the API on :8000.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
Set-Location $backend

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtualenv..." -ForegroundColor Cyan
    python -m venv .venv
}

Write-Host "Installing dependencies..." -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m pip install --upgrade pip -q
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -q

if (-not (Test-Path (Join-Path $root ".env"))) {
    Write-Warning "No .env found at repo root. Copy .env.example to .env and set GOOGLE_API_KEY."
}

Write-Host "Starting API on http://localhost:8000 ..." -ForegroundColor Green
& .\.venv\Scripts\uvicorn.exe app.main:app --reload --port 8000
