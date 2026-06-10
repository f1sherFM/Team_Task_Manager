@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"

set "PYTHON_EXE=%ROOT%.venv\Scripts\python.exe"
set "SITE_URL=http://127.0.0.1:8000/"

if not exist "%PYTHON_EXE%" (
    echo [TTM] Python virtual environment was not found at:
    echo        %PYTHON_EXE%
    echo.
    echo [TTM] Create the environment first, then try again.
    pause
    exit /b 1
)

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":8000 .*LISTENING"') do (
    set "TTM_PORT_BUSY=1"
)

if defined TTM_PORT_BUSY (
    echo [TTM] Port 8000 is already in use. Opening the site in your browser.
    start "" "%SITE_URL%"
    exit /b 0
)

echo [TTM] Starting Team Task Manager on %SITE_URL%
start "" "%SITE_URL%"
"%PYTHON_EXE%" manage.py runserver 127.0.0.1:8000

endlocal
