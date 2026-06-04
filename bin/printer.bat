@echo off

set scriptPath=%~dp0\..
if /i "%~1"=="--config" (
    rem The config UI is a windowless tray app: launch it detached via pythonw
    rem (GUI subsystem, no console) and return immediately.
    start "" "%scriptPath%\.venv\Scripts\pythonw.exe" "%scriptPath%\printer_cli.py" %*
    exit /b 0
)
"%scriptPath%\.venv\Scripts\activate" && "%scriptPath%\.venv\Scripts\python" "%scriptPath%\printer_cli.py" %* && "%scriptPath%\.venv\Scripts\deactivate"
