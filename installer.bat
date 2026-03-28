@echo off
REM USB Printer Service Installer
REM Downloads and installs the USB Printer Service from GitHub

setlocal enabledelayedexpansion

echo.
echo USB Printer Service Installer
echo ==============================
echo.

REM Get user profile path
set "LIB_PATH=%USERPROFILE%\.lib"
set "REPO_NAME=usb-printer-service-main"
set "ZIP_FILE=%LIB_PATH%\usb-printer-service.zip"
set "EXTRACT_PATH=%LIB_PATH%"
set "GITHUB_URL=https://github.com/thestampr/usb-printer-service/archive/refs/heads/main.zip"

echo Installing to: %LIB_PATH%
echo.

REM Create .lib directory if it doesn't exist
if not exist "%LIB_PATH%" (
    echo Creating .lib directory...
    mkdir "%LIB_PATH%"
    if errorlevel 1 (
        echo Error: Failed to create .lib directory
        exit /b 1
    )
)

REM Download the repository
echo Downloading from: %GITHUB_URL%

REM Try using PowerShell for download (more reliable)
powershell -Command "try { [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; (New-Object Net.WebClient).DownloadFile('%GITHUB_URL%', '%ZIP_FILE%'); Write-Host 'Download completed'; exit 0 } catch { Write-Host 'Download failed: ' $_.Exception.Message; exit 1 }" 

if errorlevel 1 (
    echo Error: Download failed
    exit /b 1
)

REM Extract the ZIP file
echo Extracting repository...
echo Adding ZIP as system archive...

REM Use PowerShell to extract the ZIP
powershell -Command "try { Add-Type -AssemblyName System.IO.Compression.FileSystem; [System.IO.Compression.ZipFile]::ExtractToDirectory('%ZIP_FILE%', '%EXTRACT_PATH%'); Write-Host 'Extraction completed'; exit 0 } catch { Write-Host 'Extraction failed: ' $_.Exception.Message; exit 1 }"

if errorlevel 1 (
    echo Error: ZIP extraction failed
    exit /b 1
)

REM Run the setup.cmd script
echo.
echo Executing setup.cmd...
echo.

set "SETUP_CMD=%LIB_PATH%\%REPO_NAME%\setup.cmd"

if not exist "%SETUP_CMD%" (
    echo Error: setup.cmd not found at %SETUP_CMD%
    exit /b 1
)

call "%SETUP_CMD%"
set "SETUP_EXIT=%ERRORLEVEL%"

echo.
echo.
if %SETUP_EXIT% equ 0 (
    echo Installation completed successfully!
    pause
    exit /b 0
) else (
    echo Installation completed with errors (exit code: %SETUP_EXIT%)
    pause
    exit /b %SETUP_EXIT%
)