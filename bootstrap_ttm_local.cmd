@echo off
setlocal

set "ROOT=%~dp0"
cd /d "%ROOT%"
set "BUNDLED_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
set "PYTHON_BOOTSTRAP="

where py >nul 2>&1
if not errorlevel 1 (
    py -3.13 --version >nul 2>&1
    if not errorlevel 1 (
        set "PYTHON_BOOTSTRAP=py -3.13"
    ) else (
        py -3.12 --version >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_BOOTSTRAP=py -3.12"
        ) else (
            py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
            if not errorlevel 1 (
                set "PYTHON_BOOTSTRAP=py -3"
            )
        )
    )
)

if not defined PYTHON_BOOTSTRAP (
    if exist "%BUNDLED_PYTHON%" (
        "%BUNDLED_PYTHON%" -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_BOOTSTRAP="%BUNDLED_PYTHON%""
        )
    )
)

if not defined PYTHON_BOOTSTRAP (
    where python >nul 2>&1
    if not errorlevel 1 (
        python -c "import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>&1
        if not errorlevel 1 (
            set "PYTHON_BOOTSTRAP=python"
        )
    )
)

if not defined PYTHON_BOOTSTRAP (
    echo [TTM] No working Python bootstrap runtime was found.
    echo [TTM] Please install Python 3.12+ or make sure python/py is available in PATH.
    pause
    exit /b 1
)

echo [TTM] Rebuilding local virtual environment with %PYTHON_BOOTSTRAP%...
%PYTHON_BOOTSTRAP% -m venv "%ROOT%.venv" --clear
if errorlevel 1 (
    echo [TTM] Failed to create the local virtual environment.
    pause
    exit /b 1
)

echo [TTM] Installing dependencies...
"%ROOT%.venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1
"%ROOT%.venv\Scripts\python.exe" -m pip install -r "%ROOT%requirements.txt"
if errorlevel 1 exit /b 1

echo [TTM] Running migrations...
"%ROOT%.venv\Scripts\python.exe" manage.py migrate
if errorlevel 1 exit /b 1

echo [TTM] Local environment is ready.
endlocal
