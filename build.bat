@echo off
echo.
echo   ========================================
echo     GTA5RP Helper - Builder
echo   ========================================
echo.

echo [1/3] Installing dependencies...
pip install pywebview nuitka ordered-set zstandard --quiet 2>nul

echo [2/3] Building .exe (3-5 minutes)...
python -m nuitka --standalone --onefile --windows-console-mode=disable --include-data-dir=ui=ui --output-filename=GTA5RP_Helper.exe --company-name="Firma" --product-name="GTA5RP Helper" --file-version=1.0.0 --product-version=1.0.0 app.py

if %ERRORLEVEL%==0 (
    echo.
    echo [3/3] SUCCESS! GTA5RP_Helper.exe created!
    echo.
) else (
    echo [ERROR] Build failed!
)
pause
