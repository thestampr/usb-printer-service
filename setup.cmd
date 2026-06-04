@echo off
setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%" || (
    echo [ERROR] Failed to change directory to %REPO_ROOT%
    exit /b 1
)

REM Update/force mode: skip the "already installed" shortcut and refresh dependencies
set "FORCE=0"
if /i "%~1"=="update" set "FORCE=1"
if /i "%~1"=="/force" set "FORCE=1"

if "%FORCE%"=="1" (
    echo [INFO] Update mode: refreshing dependencies...
    goto :do_setup
)

call :check_existing_setup
if not errorlevel 1 (
    echo [SUCCESS] Project is already set up!
    exit /b 0
)

:do_setup
set "VENV_PY=%REPO_ROOT%.venv\Scripts\python.exe"

REM Reuse an existing virtual environment (update / repair): just refresh the
REM dependencies into it. No virtualenv bootstrap needed.
if exist "%VENV_PY%" goto :install_deps

REM --- Create the virtual environment (fresh install) ---
py --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Python is not installed. Attempting to install Python 3.10+...
    call :install_python
    if errorlevel 1 (
        echo [ERROR] Python installation failed.
        exit /b 1
    )
)

echo [INFO] Creating virtual environment...
REM Use the stdlib venv via the py launcher (a real interpreter, never an active
REM venv) so we never need a fragile 'pip install --user virtualenv'.
py -m venv "%REPO_ROOT%.venv" 2>nul || python -m venv "%REPO_ROOT%.venv" || goto :error

:install_deps
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment python not found at %VENV_PY%
    exit /b 1
)

"%VENV_PY%" -m pip install --upgrade pip >nul
echo [INFO] Installing project dependencies...
"%VENV_PY%" -m pip install -r requirements.txt || goto :error

call :ensure_path "%REPO_ROOT%bin"

REM PATH refresh is broadcast by add_to_path.ps1 (WM_SETTINGCHANGE).
REM Open a NEW terminal to use the 'printer' / 'open-drawer' commands.
echo [DONE] Setup complete.
exit /b 0

:ensure_path
set "TARGET=%~1"
if not exist "%TARGET%" (
    echo [WARN] %TARGET% does not exist; skipping PATH update.
    goto :eof
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%REPO_ROOT%bin\add_to_path.ps1" -Target "%TARGET%"
if errorlevel 1 echo [WARN] Could not update PATH automatically; add "%TARGET%" to your PATH manually.
goto :eof

:check_existing_setup
set "VENV_PY=%REPO_ROOT%.venv\Scripts\python.exe"

if not exist "%REPO_ROOT%.venv" exit /b 1
if not exist "%VENV_PY%" exit /b 1

"%VENV_PY%" -m pip --version >nul 2>&1
if errorlevel 1 exit /b 1

exit /b 0

:install_python
py --version >nul 2>&1
if not errorlevel 1 exit /b 0

echo [INFO] Installing Python 3.11...
where winget >nul 2>&1
if errorlevel 1 (
    echo [ERROR] winget not found. Install Python 3.10+ manually from https://www.python.org/downloads/
    echo [INFO] Check "Add Python to PATH" during installation.
    exit /b 1
)

winget install -e --id Python.Python.3.11 -h >nul 2>&1
call refreshenv >nul 2>&1

py --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python installation failed. Install manually from https://www.python.org/downloads/
    exit /b 1
)

py -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] pip not found. Reinstall Python.
    exit /b 1
)

echo [SUCCESS] Python installed successfully.
exit /b 0

:error
echo [ERROR] Setup failed. See messages above for details.
exit /b 1
