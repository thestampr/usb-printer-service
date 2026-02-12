@echo off
setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0"
cd /d "%REPO_ROOT%" || (
    echo [ERROR] Failed to change directory to %REPO_ROOT%
    exit /b 1
)

call :check_existing_setup
if not errorlevel 1 (
    echo [SUCCESS] Project is already set up!
    exit /b 0
)

py --version >nul 2>&1
if errorlevel 1 (
    echo [WARN] Python is not installed. Attempting to install Python 3.10+...
    call :install_python
    if errorlevel 1 (
        echo [ERROR] Python installation failed.
        exit /b 1
    )
)

echo [INFO] Setting up virtual environment...
python -m pip install --upgrade pip >nul
python -m pip install --user virtualenv >nul || (
    echo [ERROR] Could not install virtualenv module.
    exit /b 1
)

if not exist "%REPO_ROOT%.venv" (
    python -m virtualenv .venv || goto :error
)

set "VENV_PY=%REPO_ROOT%.venv\Scripts\python.exe"
if not exist "%VENV_PY%" (
    echo [ERROR] Virtual environment python not found at %VENV_PY%
    exit /b 1
)

"%VENV_PY%" -m pip install --upgrade pip >nul
echo [INFO] Installing project dependencies...
"%VENV_PY%" -m pip install -r requirements.txt || goto :error

call :ensure_path "%REPO_ROOT%bin"

call refreshenv >nul 2>&1
echo [DONE] Setup complete.
exit /b 0

:ensure_path
set "TARGET=%~1"
if not exist "%TARGET%" (
    echo [WARN] %TARGET% does not exist; skipping PATH update.
    goto :eof
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$target = '%TARGET%'; " ^
    "$key = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Environment', $true); " ^
    "$path = $key.GetValue('Path', '', [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames); " ^
    "if ($path -split ';' -contains $target) { Write-Host '[INFO] Already in PATH: !target!' } " ^
    "else { " ^
    "   $newPath = $path + ';' + $target; " ^
    "   $key.SetValue('Path', $newPath, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames); " ^
    "   Write-Host '[INFO] Added to PATH: !target!' " ^
    "}"
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
