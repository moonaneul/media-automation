$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host ""
Write-Host "=== media-automation Windows setup ==="
Write-Host ""

if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
    throw "Python Launcher(py)가 없습니다. Python 3.11+를 먼저 설치하세요."
}

if (-not (Test-Path ".venv")) {
    Write-Host "[1/4] Creating virtual environment..."
    py -3 -m venv .venv
}
else {
    Write-Host "[1/4] .venv already exists."
}

Write-Host "[2/4] Activating virtual environment..."
& ".\.venv\Scripts\Activate.ps1"

Write-Host "[3/4] Installing dependencies..."
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

Write-Host "[4/4] Running tests..."
python -m pytest

Write-Host ""
Write-Host "Checking Windows / PowerPoint COM..."
python scripts/check_windows.py

Write-Host ""
Write-Host "=== Setup complete ==="
