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
