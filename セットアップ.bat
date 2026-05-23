@echo off
rem ===================================================================
rem  Paper Management launcher (pure ASCII; no Japanese inside).
rem  "%~dpn0.py" resolves to the .py file with the SAME name as this
rem  .bat, so editing this filename is enough -- no path is hardcoded.
rem ===================================================================
chcp 65001 >nul
cd /d "%~dp0"

if not exist "%~dp0uv.exe" (
    echo [ERROR] uv.exe was not found next to this file.
    echo Please extract the full distribution ZIP again without leaving files out.
    pause
    exit /b 1
)

rem --no-project: fetch only Python now; the .py script runs "uv sync" itself
rem so the large dependency download shows visible progress.
"%~dp0uv.exe" run --no-project python "%~dpn0.py"
