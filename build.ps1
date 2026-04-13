# ═══════════════════════════════════════════
# GTA5RP Helper — Build Script (Windows)
# ═══════════════════════════════════════════
#
# Требования:
#   pip install pywebview nuitka ordered-set zstandard
#
# Запуск:
#   powershell -ExecutionPolicy Bypass -File build.ps1
#

Write-Host ""
Write-Host "  ╔══════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "  ║     GTA5RP Helper — Builder      ║" -ForegroundColor Cyan
Write-Host "  ╚══════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Проверяем зависимости
Write-Host "[1/3] Checking dependencies..." -ForegroundColor Yellow
pip install pywebview nuitka ordered-set zstandard --quiet 2>$null

# Сборка
Write-Host "[2/3] Building .exe with Nuitka..." -ForegroundColor Yellow
Write-Host "       This may take 3-5 minutes..." -ForegroundColor DarkGray

python -m nuitka `
    --standalone `
    --onefile `
    --windows-console-mode=disable `
    --include-data-dir=ui=ui `
    --output-filename=GTA5RP_Helper.exe `
    --company-name="Firma" `
    --product-name="GTA5RP Helper" `
    --file-description="GTA5RP Business Helper" `
    --file-version=1.0.0 `
    --product-version=1.0.0 `
    app.py

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[3/3] Done!" -ForegroundColor Green
    Write-Host ""
    Write-Host "  GTA5RP_Helper.exe created successfully!" -ForegroundColor Green
    Write-Host "  File: $(Get-Location)\GTA5RP_Helper.exe" -ForegroundColor DarkGray
    Write-Host ""
} else {
    Write-Host "[ERROR] Build failed!" -ForegroundColor Red
}
