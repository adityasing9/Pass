# PASS (passx) Windows One-Line Installer
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  Installing PASS (passx)..." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan

# Check Python
$pythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    Write-Host "Python was not found on your system." -ForegroundColor Red
    Write-Host "Please install Python 3.8+ from https://www.python.org/ or the Microsoft Store." -ForegroundColor Yellow
    exit 1
}

Write-Host "Installing PASS directly from GitHub archive (no git clone required)..." -ForegroundColor Cyan
& python -m pip install --upgrade --no-cache-dir "https://github.com/adityasing9/Pass/archive/refs/heads/main.zip"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nPASS installed successfully!" -ForegroundColor Green
    Write-Host "Run 'passx' from any terminal to get started." -ForegroundColor Cyan
    & passx version
} else {
    Write-Host "Installation failed. Please verify your Python and pip installation." -ForegroundColor Red
}
