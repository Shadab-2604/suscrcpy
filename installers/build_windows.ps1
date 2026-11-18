# ==============================================================================
# SUSCRCPY 2.0 — Windows PyInstaller Executable Builder
# ==============================================================================
# Builds a standalone Windows .exe with PyInstaller

$ErrorActionPreference = "Stop"

Write-Host "=== SUSCRCPY 2.0 Windows Build Script ===" -ForegroundColor Cyan

# Ensure PyInstaller is installed
Write-Host "[+] Ensuring PyInstaller is installed..." -ForegroundColor Cyan
python -m pip install --upgrade pyinstaller

# Run PyInstaller using spec file
Write-Host "[+] Building standalone executable..." -ForegroundColor Cyan
Set-Location "$PSScriptRoot\.."
pyinstaller --clean -y suscrcpy.spec

Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "[✓] Build complete! Executable is available in 'dist\suscrcpy\suscrcpy.exe'" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
