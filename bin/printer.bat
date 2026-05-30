@echo off

set scriptPath=%~dp0\..
if exist "%scriptPath%\.venv\Scripts\python.exe" (
    "%scriptPath%\.venv\Scripts\python.exe" "%scriptPath%\printer_cli.py" %*
) else (
    python "%scriptPath%\printer_cli.py" %*
)

