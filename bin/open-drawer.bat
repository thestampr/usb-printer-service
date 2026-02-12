@echo off

set scriptPath=%~dp0\..
"%scriptPath%\.venv\Scripts\activate" && "%scriptPath%\.venv\Scripts\python" "%scriptPath%\drawer_cli.py" %* && "%scriptPath%\.venv\Scripts\deactivate"
