@echo off
REM Build bratbox.exe on Windows
REM Requires: Python 3.10-3.13 recommended (pygame has no 3.14 wheels yet)

setlocal
cd /d "%~dp0"

echo Checking Python version...
python -c "import sys; v=sys.version_info; exit(0 if v.major==3 and 10 <= v.minor <= 13 else 1)" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo WARNING: Python 3.10-3.13 recommended. pygame may not install on other versions.
    echo If the build fails, install Python 3.12 from python.org and try again.
    echo.
)

echo Installing PyInstaller...
python -m pip install --upgrade pyinstaller windows-curses

echo Installing pygame...
python -m pip install pygame 2>nul
python -c "import pygame" 2>nul
if %errorlevel% neq 0 (
    echo pygame failed, trying pygame-ce (community edition, drop-in replacement)...
    python -m pip install pygame-ce
)
python -c "import pygame" 2>nul
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Could not install pygame or pygame-ce.
    echo Try installing Python 3.12 from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)
echo pygame OK.

echo.
echo Building bratbox.exe (this takes a few minutes)...
python -m PyInstaller bratbox.spec --clean --noconfirm

echo.
if exist "dist\bratbox.exe" (
    echo SUCCESS: dist\bratbox.exe
    for %%f in ("dist\bratbox.exe") do echo Size: %%~zf bytes
) else (
    echo FAILED: exe not found - check the PyInstaller output above
)
pause
