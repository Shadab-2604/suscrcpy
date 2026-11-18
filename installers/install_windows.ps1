# ==============================================================================
# SUSCRCPY 2.0 — Windows Installation Script (Windows 10 / 11)
# ==============================================================================
# Run with PowerShell (Run as Administrator recommended for start menu shortcuts)

$ErrorActionPreference = "Stop"

Write-Host "=== SUSCRCPY 2.0 Windows Installer ===" -ForegroundColor Cyan

# 1. Verify Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[✓] Found Python: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Error "Python 3.11+ is required. Install Python from https://www.python.org/downloads/ and ensure 'Add Python to PATH' is checked."
    exit 1
}

# 2. Verify ADB and scrcpy
$adbFound = Get-Command adb -ErrorAction SilentlyContinue
$scrcpyFound = Get-Command scrcpy -ErrorAction SilentlyContinue

if (-not $adbFound) {
    Write-Host "[!] 'adb.exe' was not found in PATH." -ForegroundColor Yellow
    Write-Host "    Download Android SDK Platform-Tools or scrcpy release containing adb.exe." -ForegroundColor Yellow
} else {
    Write-Host "[✓] Found ADB: $($adbFound.Source)" -ForegroundColor Green
}

if (-not $scrcpyFound) {
    Write-Host "[!] 'scrcpy.exe' was not found in PATH." -ForegroundColor Yellow
    Write-Host "    Download official scrcpy from https://github.com/Genymobile/scrcpy/releases" -ForegroundColor Yellow
    Write-Host "    and add its folder to your system PATH." -ForegroundColor Yellow
} else {
    Write-Host "[✓] Found scrcpy: $($scrcpyFound.Source)" -ForegroundColor Green
}

# 3. Install Python dependencies
Write-Host "`n[+] Installing required Python packages (PySide6)..." -ForegroundColor Cyan
python -m pip install --upgrade pip
python -m pip install -r "$PSScriptRoot\..\requirements.txt"

# 4. Create Desktop Shortcut
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "SUSCRCPY 2.0.lnk"
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut($shortcutPath)
$mainScript = (Resolve-Path "$PSScriptRoot\..\main.py").Path
$shortcut.TargetPath = "pythonw.exe"
$shortcut.Arguments = "`"$mainScript`""
$shortcut.WorkingDirectory = (Resolve-Path "$PSScriptRoot\..").Path
$shortcut.Description = "SUSCRCPY 2.0 Android Device Testing Application"
$shortcut.Save()

Write-Host "`n==============================================================================" -ForegroundColor Green
Write-Host "[✓] Installation complete! Desktop shortcut created: $shortcutPath" -ForegroundColor Green
Write-Host "To launch from command prompt or terminal:" -ForegroundColor Green
Write-Host "    python main.py" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Green
