@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"

if not exist "%PYTHON_EXE%" goto :missing
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 goto :missing

"%PYTHON_EXE%" manage.py test %*
exit /b %errorlevel%

:missing
echo [TTM] Local Python environment is missing or invalid.
echo [TTM] Run bootstrap_ttm_local.cmd first.
pause
exit /b 1
