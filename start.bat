@echo off
title GTA5RP Helper Bot
color 0A
cd /d "%~dp0"

echo ============================================
echo   GTA5RP Helper Bot
echo ============================================
echo.
echo   Directory: %cd%
echo.

python --version >/dev/null 2>/dev/null
if errorlevel 1 (
    echo [!] Python not found!
    pause
    exit
)

echo [*] Installing dependencies...
pip install pydirectinput pyautogui pillow requests >/dev/null 2>/dev/null
echo [+] Done!
echo.

python "%~dp0helper.py"
pause
