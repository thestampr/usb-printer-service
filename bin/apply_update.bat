@echo off
REM Detached updater invoked by the in-app update checker.
REM Usage: apply_update.bat <install_root> <wait_pid> <relaunch: ui|none>
REM Waits for the app (wait_pid) to exit, then downloads, installs, refreshes
REM dependencies, and optionally reopens the app. Runs from a %TEMP% copy so it
REM can overwrite its own bin\ original safely.

setlocal enabledelayedexpansion

set "ROOT=%~1"
set "WAIT_PID=%~2"
set "RELAUNCH=%~3"
if "%ROOT%"=="" (
    echo [ERROR] No install root provided.
    pause
    exit /b 1
)
if "%RELAUNCH%"=="" set "RELAUNCH=none"

set "REPO_NAME=usb-printer-service-main"
set "GITHUB_URL=https://github.com/thestampr/usb-printer-service/archive/refs/heads/main.zip"
set "TMP_DIR=%TEMP%\ups_update_%RANDOM%%RANDOM%"
set "ZIP_FILE=%TMP_DIR%\update.zip"
set "EXTRACT_DIR=%TMP_DIR%\extract"

echo.
echo USB Printer Service Updater
echo ==============================
echo Target: %ROOT%
echo.

REM Wait for the running app to close so its files/DLLs are released
if not "%WAIT_PID%"=="" (
    echo Waiting for the application to close ^(PID %WAIT_PID%^)...
    :waitloop
    tasklist /FI "PID eq %WAIT_PID%" 2>nul | find "%WAIT_PID%" >nul
    if not errorlevel 1 (
        timeout /t 1 /nobreak >nul
        goto :waitloop
    )
)

mkdir "%TMP_DIR%" 2>nul

echo Downloading latest version...
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%GITHUB_URL%', '%ZIP_FILE%'); exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo [ERROR] Download failed.
    goto :fail
)

echo Extracting...
powershell -NoProfile -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP_FILE%', '%EXTRACT_DIR%'); exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 (
    echo [ERROR] Extraction failed.
    goto :fail
)

set "SRC=%EXTRACT_DIR%\%REPO_NAME%"
if not exist "%SRC%\setup.cmd" (
    echo [ERROR] Update payload is invalid.
    goto :fail
)

echo Installing files...
REM /E preserves items not in the archive (.venv, config\temp.settings.json, custom images)
robocopy "%SRC%" "%ROOT%" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul
if %ERRORLEVEL% GEQ 8 (
    echo [ERROR] Failed to copy files ^(robocopy code %ERRORLEVEL%^).
    goto :fail
)

echo Refreshing dependencies...
call "%ROOT%\setup.cmd" update

rmdir /s /q "%TMP_DIR%" 2>nul

echo.
echo [DONE] Update complete.

if /i "%RELAUNCH%"=="ui" (
    echo Reopening configuration...
    powershell -NoProfile -Command "Start-Process -FilePath '%ROOT%\bin\printer.bat' -ArgumentList '--config' -WindowStyle Hidden"
)

timeout /t 2 /nobreak >nul
exit /b 0

:fail
rmdir /s /q "%TMP_DIR%" 2>nul
echo.
echo [ERROR] Update failed. Your existing installation was left in place.
pause
exit /b 1
