@echo off
rem Open the configuration UI with no console window (pythonw = GUI subsystem),
rem detached so the shell returns immediately. Extra args (e.g. --minimized) pass through.

set scriptPath=%~dp0\..
start "" "%scriptPath%\.venv\Scripts\pythonw.exe" "%scriptPath%\printer_cli.py" --config %*
