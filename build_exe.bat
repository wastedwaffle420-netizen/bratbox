@echo off
REM Build bratbox.exe on Windows
REM Requires: Python 3.10+, pip

setlocal
cd /d "%~dp0"

echo Installing PyInstaller...
python -m pip install --upgrade pyinstaller pygame windows-curses

echo.
echo Building bratbox.exe (this takes a few minutes)...
python -m PyInstaller bratbox.spec --clean --noconfirm

echo.
if exist "dist\bratbox.exe" (
    echo SUCCESS: dist\bratbox.exe
    for %%f in ("dist\bratbox.exe") do echo Size: %%~zf bytes
) else (
    echo FAILED: exe not found
)
pause
