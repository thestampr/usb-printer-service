@echo off
REM USB Printer Service Installer / Updater
REM Auto-detects an existing install and updates it; otherwise performs a fresh install.

setlocal enabledelayedexpansion

REM Paths
set "LIB_PATH=%USERPROFILE%\.lib"
set "REPO_NAME=usb-printer-service-main"
set "REPO_DIR=%LIB_PATH%\%REPO_NAME%"
set "ZIP_FILE=%LIB_PATH%\usb-printer-service.zip"
set "EXTRACT_TMP=%LIB_PATH%\_extract_tmp"
set "GITHUB_URL=https://github.com/thestampr/usb-printer-service/archive/refs/heads/main.zip"

REM Auto-detect mode: update when an existing install is found, otherwise install
set "MODE=install"
if exist "%REPO_DIR%\setup.cmd" set "MODE=update"

echo.
if "%MODE%"=="update" (
    echo USB Printer Service Updater
    echo ==============================
    echo Updating existing installation at: %REPO_DIR%
) else (
    echo USB Printer Service Installer
    echo ==============================
    echo Installing to: %LIB_PATH%
)
echo.

REM Create the base directory if needed
if not exist "%LIB_PATH%" (
    echo Creating .lib directory...
    mkdir "%LIB_PATH%"
    if errorlevel 1 (
        echo Error: Failed to create .lib directory
        exit /b 1
    )
)

REM Download the repository archive
echo Downloading from: %GITHUB_URL%
powershell -NoProfile -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%GITHUB_URL%', '%ZIP_FILE%'); Write-Host 'Download completed'; exit 0 } catch { Write-Host ('Download failed: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo Error: Download failed
    exit /b 1
)

REM Extract to a temp folder first; extracting onto an existing folder would fail
if exist "%EXTRACT_TMP%" rmdir /s /q "%EXTRACT_TMP%"

echo Extracting repository...
powershell -NoProfile -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP_FILE%', '%EXTRACT_TMP%'); Write-Host 'Extraction completed'; exit 0 } catch { Write-Host ('Extraction failed: ' + $_.Exception.Message); exit 1 }"
if errorlevel 1 (
    echo Error: ZIP extraction failed
    del /q "%ZIP_FILE%" 2>nul
    exit /b 1
)

set "SRC_DIR=%EXTRACT_TMP%\%REPO_NAME%"
if not exist "%SRC_DIR%\setup.cmd" (
    echo Error: Extracted contents not found at %SRC_DIR%
    exit /b 1
)

REM Copy the new source over the target directory.
REM /E adds and overwrites files from the archive while leaving items NOT in the archive
REM intact - so on update the user's .venv and config\temp.settings.json (both gitignored,
REM hence absent from the download) are preserved.
echo Copying files to %REPO_DIR% ...
robocopy "%SRC_DIR%" "%REPO_DIR%" /E /NFL /NDL /NJH /NJS /NC /NS /NP >nul
if %ERRORLEVEL% GEQ 8 (
    echo Error: Failed to copy files ^(robocopy code %ERRORLEVEL%^)
    exit /b 1
)

REM Clean up temporary artifacts
rmdir /s /q "%EXTRACT_TMP%" 2>nul
del /q "%ZIP_FILE%" 2>nul

REM Run setup. In update mode, pass "update" to force a dependency refresh.
set "SETUP_CMD=%REPO_DIR%\setup.cmd"
if not exist "%SETUP_CMD%" (
    echo Error: setup.cmd not found at %SETUP_CMD%
    exit /b 1
)

echo.
echo Executing setup.cmd...
echo.
if "%MODE%"=="update" (
    call "%SETUP_CMD%" update
) else (
    call "%SETUP_CMD%"
)
set "SETUP_EXIT=%ERRORLEVEL%"

echo.
echo.
if %SETUP_EXIT% equ 0 (
    if "%MODE%"=="update" (
        echo Update completed successfully!
    ) else (
        echo Installation completed successfully!
    )
    echo Open a NEW terminal, then run: printer --help
    pause
    exit /b 0
) else (
    echo Completed with errors ^(exit code: %SETUP_EXIT%^)
    pause
    exit /b %SETUP_EXIT%
)
