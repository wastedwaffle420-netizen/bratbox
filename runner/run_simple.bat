@echo off
REM bird box — Birdsong v11 (Windows)
REM rhythm-only terminal build. No browser, no ElevenLabs, no live LLM.
REM
REM Requires: python, windows-curses, pygame
REM   pip install windows-curses pygame

setlocal

set RUNNER_DIR=%~dp0
set GAME_DIR=%RUNNER_DIR%..\ogre_director_v2

where python >nul 2>nul
if %errorlevel%==0 ( set PY=python ) else ( set PY=py )

REM Auto-install required packages if missing (pygame for audio, windows-curses for display)
%PY% -c "import pygame" 2>nul
if %errorlevel% neq 0 (
    echo Installing pygame...
    %PY% -m pip install pygame
)
%PY% -c "import curses" 2>nul
if %errorlevel% neq 0 (
    echo Installing windows-curses...
    %PY% -m pip install windows-curses
)

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format 'yyyyMMdd_HHmmss'"') do set STAMP=%%i
set SESSION=%RUNNER_DIR%runs\%STAMP%
mkdir "%SESSION%" 2>nul

set BRATBOX_UNBROKEN=1
set BRATBOX_RHYTHM_ONLY=1
echo. > "%GAME_DIR%\rhythm_only.txt"
set LOCKKEY_INTENSITY=rough
set LOCKKEY_OGRE_EXPERIENCE_MODE=elastic_grotesque
set JASMINE_DIRECTOR=1
set JASMINE_DIRECTOR_WAIT_MS=250
set JASMINE_AUDIO_ONLY=1
set JASMINE_VOICE_GAP_S=0.6
set JASMINE_VOICE_OVERLAP=1.0
set LOCKKEY_VOICE_COOLDOWN_MS=600
set JASMINE_TTS_PROVIDERS=deck
set JASMINE_VOICE_DECK=%GAME_DIR%\assets\audio\jasmine
set JASMINE_FIFO_DIR=%SESSION%\fifo
set BRATBOX_SESSION=%SESSION%

echo session: %SESSION%
echo mode: rhythm-only / intensity=rough / bed=elastic_grotesque
echo voice: glossy pendant (her) + mild yarn (him), offline deck
echo build: v11-windows-20260925-1646
echo.

REM start director + operator, save PIDs for cleanup
for /f %%p in ('powershell -NoProfile -Command "$d=Start-Process '%PY%' -ArgumentList '\"%RUNNER_DIR%director.py\"','--session','\"%SESSION%\"' -RedirectStandardOutput '\"%SESSION%\director_stdout.log\"' -RedirectStandardError '\"%SESSION%\director_stdout.log\"' -WindowStyle Hidden -PassThru; $d.Id"') do set DPID=%%p
for /f %%p in ('powershell -NoProfile -Command "$w=Start-Process '%PY%' -ArgumentList '\"%RUNNER_DIR%offline_writer.py\"','\"%SESSION%\"' -RedirectStandardOutput '\"%SESSION%\writer_stdout.log\"' -RedirectStandardError '\"%SESSION%\writer_stdout.log\"' -WindowStyle Hidden -PassThru; $w.Id"') do set WPID=%%p

timeout /t 2 /nobreak >nul

REM game in the foreground
%PY% "%GAME_DIR%\ogre_shader_v5.py"

echo.
echo shutting down the night...
if defined DPID taskkill /pid %DPID% /f >nul 2>nul
if defined WPID taskkill /pid %WPID% /f >nul 2>nul
echo done. session: %SESSION%
