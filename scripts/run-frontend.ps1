# Run the frontend locally on Windows.
#   ./scripts/run-frontend.ps1
# Installs npm deps (if missing) and starts the Vite dev server on :5173.

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"
Set-Location $frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm dependencies..." -ForegroundColor Cyan
    npm install
}

Write-Host "Starting Vite dev server on http://localhost:5173 ..." -ForegroundColor Green
npm run dev
