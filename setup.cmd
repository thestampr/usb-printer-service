@echo off
setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%" || (
    echo [ERROR] Failed to change directory to %REPO_ROOT%
    exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not on PATH. Install Python 3.10+ and try again.
    exit /b 1
)

echo [INFO] Ensuring virtualenv is available...
python -m pip install --upgrade pip >nul
python -m pip install --user virtualenv >nul || (
    echo [ERROR] Could not install virtualenv module.
    exit /b 1
)

if exist "%REPO_ROOT%.venv" (
    echo [INFO] Existing .venv detected. Skipping creation.
) else (
    echo [INFO] Creating virtual environment in .venv ...
    python -m virtualenv .venv || goto :error
)

set "VENV_PY=%REPO_ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment python not found at %VENV_PY%
    exit /b 1
)

echo [INFO] Installing project requirements...
"%VENV_PY%" -m pip install --upgrade pip >nul
"%VENV_PY%" -m pip install -r requirements.txt || goto :error

call :ensure_path "%REPO_ROOT%bin"

echo [DONE] Setup complete. Open a new terminal session to use the updated PATH and activate the venv via .\.venv\Scripts\activate.
exit /b 0

:ensure_path
set "TARGET=%~1"
if not exist "%TARGET%" (
    echo [WARN] %TARGET% does not exist; skipping PATH update.
    goto :eof
)
set "CURRENT_PATH="
for /f "tokens=1*" %%A in ('reg query "HKCU\Environment" /v PATH 2^>nul ^| findstr /R /C:"PATH"') do (
    set "CURRENT_PATH=%%B"
)
if not defined CURRENT_PATH set "CURRENT_PATH=%PATH%"

echo !CURRENT_PATH! | findstr /I /C:"%TARGET%" >nul
if errorlevel 1 (
    echo [INFO] Adding %TARGET% to user PATH...
    setx PATH "!CURRENT_PATH!;%TARGET%" >nul
) else (
    echo [INFO] %TARGET% already present in PATH. Skipping.
)
goto :eof

:error
echo [ERROR] Setup failed. See messages above for details.
exit /b 1
