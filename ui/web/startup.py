"""Manage the "Run at startup" Windows setting (per-user Run registry key).

Adds/removes an ``HKCU\\...\\Run`` entry that launches the app minimized into the
system tray at sign-in. The registry entry's presence is the source of truth.
"""

from __future__ import annotations

import os
import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "PrinterReceiptService"
# Our own key, used to remember that the "on by default" has been applied once so
# we never re-enable after the user opts out. In the registry (not config/) so it
# survives updates/re-installs.
_APP_KEY = r"Software\PrinterReceiptService"
_DEFAULT_MARK = "StartupDefaulted"
_ROOT = Path(__file__).resolve().parents[2]
_CLI = _ROOT / "printer_cli.py"


def _command() -> str:
    """The command Windows runs at sign-in (starts hidden in the tray)."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" --config --minimized'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    runner = pyw if os.path.exists(pyw) else sys.executable
    return f'"{runner}" "{_CLI}" --config --minimized'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
            return True
    except OSError:
        return False


def enable() -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _command())


def disable() -> None:
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _default_applied() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _APP_KEY) as key:
            winreg.QueryValueEx(key, _DEFAULT_MARK)
            return True
    except OSError:
        return False


def _mark_default_applied() -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _APP_KEY) as key:
        winreg.SetValueEx(key, _DEFAULT_MARK, 0, winreg.REG_SZ, "1")


def apply_default() -> None:
    """Enable Run-at-startup the first time only (on by default, opt-out).

    Runs once per machine; after the user toggles the setting their choice is
    respected and this never re-enables it.
    """
    if _default_applied():
        return
    try:
        enable()
    except OSError:
        pass
    try:
        _mark_default_applied()
    except OSError:
        pass
