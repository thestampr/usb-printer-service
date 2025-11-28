@echo off
setlocal
cd /d "%~dp0"
.venv\Scripts\activate && .venv\Scripts\python cli.py %* && .venv\Scripts\deactivate
endlocal
