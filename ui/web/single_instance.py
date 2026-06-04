"""Single-instance guard shared by the config UI.

Reuses the same named mutex and window-title the legacy Tkinter UI used, so the
two never run at once during the migration and foregrounding keeps working.
"""

from __future__ import annotations

import atexit
import ctypes
from typing import Optional

_MUTEX_NAME = "Global\\PrinterConfigMutex"


def _acquire_mutex() -> Optional[int]:
    """Create the named mutex; return its handle, or None if already held/failed."""
    try:
        k32 = ctypes.windll.kernel32
        handle = k32.CreateMutexW(None, False, _MUTEX_NAME)
        if not handle:
            return None
        already = k32.GetLastError() == 183  # ERROR_ALREADY_EXISTS
        if already:
            k32.CloseHandle(handle)
            return None
        return handle
    except Exception:
        return None


def ensure_single_instance(window_title: str) -> bool:
    """Return True if this is the only instance.

    When another instance already holds the mutex, signal it to surface its
    window (it may be hidden in the tray) and return False so the caller exits.
    """
    mutex = _acquire_mutex()
    if mutex is None:
        try:
            from ui.web.tray import signal_show

            if not signal_show():
                # Fallback: the tray window isn't up yet — try title foreground.
                from ui.utils.winapi import WindowFrame, get_window_from_title

                WindowFrame.foreground(get_window_from_title(window_title))
        except Exception:
            pass
        return False

    atexit.register(lambda: ctypes.windll.kernel32.ReleaseMutex(mutex) if mutex else None)
    return True
