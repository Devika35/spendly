# setup.ps1 - one-shot Windows setup for expense-tracker
# Run from project folder:  powershell -ExecutionPolicy Bypass -File .\setup.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$sysPy = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
$venvPy = ".\venv\Scripts\python.exe"

if (-not (Test-Path $venvPy)) {
    Write-Host "Creating venv..." -ForegroundColor Cyan
    & $sysPy -m venv venv
}

Write-Host "Python in venv:" -ForegroundColor Cyan
& $venvPy --version

Write-Host "Upgrading pip..." -ForegroundColor Cyan
& $venvPy -m pip install --upgrade pip

Write-Host "Installing requirements..." -ForegroundColor Cyan
& $venvPy -m pip install -r requirements.txt

Write-Host "Installed packages:" -ForegroundColor Cyan
& $venvPy -m pip list

Write-Host "`nDone. Activate with:  .\venv\Scripts\Activate.ps1" -ForegroundColor Green
