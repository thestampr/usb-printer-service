"""Windows notification-area (system tray) icon + native context menu.

Uses pywin32 only (already a dependency). The icon needs a hidden message window
pumping its own message loop on a dedicated thread to receive click callbacks;
``Shell_NotifyIcon`` add/remove/modify must run on that same thread, so external
calls are marshaled in via ``PostMessage``. The right-click menu is a real native
``TrackPopupMenu`` (not an app window), themed dark on Windows 11.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from pathlib import Path
from typing import Callable, Dict, Optional

import win32api
import win32con
import win32gui

_TRAY_CLASS = "PrinterServiceTrayWnd"
_ICON_DIR = Path(__file__).resolve().parents[2] / "assets" / "tray"

# Tray callback message + marshaling messages handled on the tray thread.
_WM_TRAY = win32con.WM_USER + 20
_WM_DO_ADD = win32con.WM_USER + 21
_WM_DO_DELETE = win32con.WM_USER + 22
_WM_DO_TIP = win32con.WM_USER + 23
# Cross-process "show the main window" signal (a second instance posts this).
_WM_SHOW = win32con.WM_USER + 30


def signal_show() -> bool:
    """Tell an already-running instance to surface its window. Returns True if found."""
    try:
        hwnd = win32gui.FindWindow(_TRAY_CLASS, None)
    except Exception:
        hwnd = 0
    if hwnd:
        # Grant the running instance permission to steal focus (bypasses the
        # foreground lock) so its window can actually come to the front.
        try:
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            ctypes.windll.user32.AllowSetForegroundWindow(pid.value)
        except Exception:
            pass
        win32gui.PostMessage(hwnd, _WM_SHOW, 0, 0)
        return True
    return False

# Menu command ids.
_ID_OPEN = 1
_ID_START = 2
_ID_STOP = 3
_ID_RESTART_SVC = 4
_ID_CHECK_UPDATE = 5
_ID_RESTART_APP = 6
_ID_QUIT = 7
_CMD_TO_ACTION = {
    _ID_OPEN: "open",
    _ID_START: "start",
    _ID_STOP: "stop",
    _ID_RESTART_SVC: "restart",
    _ID_CHECK_UPDATE: "check_update",
    _ID_RESTART_APP: "restart_app",
    _ID_QUIT: "quit",
}

_MIIM_BITMAP = 0x00000080


class _MENUITEMINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT), ("fMask", wintypes.UINT), ("fType", wintypes.UINT),
        ("fState", wintypes.UINT), ("wID", wintypes.UINT), ("hSubMenu", wintypes.HMENU),
        ("hbmpChecked", wintypes.HANDLE), ("hbmpUnchecked", wintypes.HANDLE),
        ("dwItemData", ctypes.c_void_p), ("dwTypeData", wintypes.LPWSTR),
        ("cch", wintypes.UINT), ("hbmpItem", wintypes.HANDLE),
    ]


_gdiplus_token = None


def _gdiplus_start() -> bool:
    global _gdiplus_token
    if _gdiplus_token is not None:
        return True
    try:
        class _StartupInput(ctypes.Structure):
            _fields_ = [
                ("GdiplusVersion", ctypes.c_uint32), ("DebugEventCallback", ctypes.c_void_p),
                ("SuppressBackgroundThread", ctypes.c_int32), ("SuppressExternalCodecs", ctypes.c_int32),
            ]
        token = ctypes.c_void_p()
        ctypes.windll.gdiplus.GdiplusStartup(
            ctypes.byref(token), ctypes.byref(_StartupInput(1, None, 0, 0)), None
        )
        _gdiplus_token = token
        return True
    except Exception:
        return False


def _load_hbitmap(path: str):
    """Load a PNG into a premultiplied 32bpp ARGB HBITMAP (renders with alpha in menus)."""
    if not _gdiplus_start():
        return None
    try:
        g = ctypes.windll.gdiplus
        bitmap = ctypes.c_void_p()
        if g.GdipCreateBitmapFromFile(ctypes.c_wchar_p(path), ctypes.byref(bitmap)) != 0:
            return None
        hbm = ctypes.c_void_p()
        g.GdipCreateHBITMAPFromBitmap(bitmap, ctypes.byref(hbm), 0)  # 0 = transparent bg
        g.GdipDisposeImage(bitmap)
        return hbm.value
    except Exception:
        return None


def _enable_dark_menus() -> None:
    """Opt the process into dark mode so native popup menus render dark (Win10+)."""
    try:
        uxtheme = ctypes.WinDLL("uxtheme")
        set_app_mode = uxtheme[135]  # SetPreferredAppMode(PreferredAppMode)
        set_app_mode.argtypes = [ctypes.c_int]
        set_app_mode.restype = ctypes.c_int
        set_app_mode(2)  # ForceDark
        uxtheme[136]()   # FlushMenuThemes()
    except Exception:
        pass


class Tray:
    """A single tray icon with a native right-click menu. Callbacks run on the
    tray thread; ``actions`` maps "open"/"restart"/"stop"/"quit" to callables and
    ``state_provider`` returns ``{running, host, port}`` for the menu header."""

    def __init__(
        self,
        icon_path: str,
        tooltip: str = "",
        on_left_click: Optional[Callable[[], None]] = None,
        actions: Optional[Dict[str, Callable[[], None]]] = None,
        state_provider: Optional[Callable[[], dict]] = None,
    ) -> None:
        self._icon_path = str(icon_path)
        self._tooltip = tooltip
        self._on_left = on_left_click
        self._actions = actions or {}
        self._state = state_provider or (lambda: {"running": False})
        self._hwnd: Optional[int] = None
        self._hicon = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._visible = False
        self._icons: Dict[str, int] = {}  # name -> HBITMAP cache (tray-thread)

    # -- public API (callable from any thread) ---------------------------

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="tray", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def show_icon(self) -> None:
        self._post(_WM_DO_ADD)

    def hide_icon(self) -> None:
        self._post(_WM_DO_DELETE)

    def set_tooltip(self, text: str) -> None:
        self._tooltip = text
        self._post(_WM_DO_TIP)

    def stop(self) -> None:
        if self._hwnd:
            win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    # -- internals (tray thread) -----------------------------------------

    def _post(self, msg: int) -> None:
        if self._hwnd:
            win32gui.PostMessage(self._hwnd, msg, 0, 0)

    def _nid(self):
        flags = win32gui.NIF_ICON | win32gui.NIF_MESSAGE | win32gui.NIF_TIP
        return (self._hwnd, 0, flags, _WM_TRAY, self._hicon, self._tooltip)

    def _run(self) -> None:
        _enable_dark_menus()
        hinst = win32gui.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = hinst
        wc.lpszClassName = _TRAY_CLASS
        wc.lpfnWndProc = self._wndproc
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error:
            pass  # already registered in this process
        self._hwnd = win32gui.CreateWindow(
            wc.lpszClassName, "PrinterServiceTray", 0, 0, 0, 0, 0, 0, 0, hinst, None
        )
        win32gui.UpdateWindow(self._hwnd)
        try:
            self._hicon = win32gui.LoadImage(
                0, self._icon_path, win32con.IMAGE_ICON, 0, 0,
                win32con.LR_LOADFROMFILE | win32con.LR_DEFAULTSIZE,
            )
        except Exception:
            self._hicon = win32gui.LoadIcon(0, win32con.IDI_APPLICATION)
        self._ready.set()
        win32gui.PumpMessages()

    def _safe(self, fn: Optional[Callable[[], None]]) -> None:
        if fn is None:
            return
        try:
            fn()
        except Exception:
            pass

    def _icon(self, name: str):
        """HBITMAP for assets/tray/<name>.png, cached for the tray's lifetime."""
        if name not in self._icons:
            self._icons[name] = _load_hbitmap(str(_ICON_DIR / (name + ".png"))) or 0
        return self._icons[name] or None

    def _show_menu(self) -> None:
        """Pop the Docker-style native context menu at the cursor (tray thread)."""
        try:
            state = self._state()
        except Exception:
            state = {"running": False}
        running = bool(state.get("running"))

        menu = win32gui.CreatePopupMenu()
        pos = [0]

        def item(flags, cmd_id, text, icon=None):
            win32gui.AppendMenu(menu, flags, cmd_id, text)
            if icon:
                hbm = self._icon(icon)
                if hbm:
                    mii = _MENUITEMINFO()
                    mii.cbSize = ctypes.sizeof(_MENUITEMINFO)
                    mii.fMask = _MIIM_BITMAP
                    mii.hbmpItem = hbm
                    ctypes.windll.user32.SetMenuItemInfoW(menu, pos[0], True, ctypes.byref(mii))
            pos[0] += 1

        sep = win32con.MF_SEPARATOR
        run_flag = win32con.MF_STRING | (0 if running else win32con.MF_GRAYED)

        # Status header (Docker-style: dot + state), then grouped sections.
        # Kept enabled (not MF_DISABLED) so the colored status dot isn't
        # desaturated; id 0 maps to no action, so it's effectively inert.
        item(win32con.MF_STRING,
             0, "Service is running" if running else "Service is stopped",
             "dot_on" if running else "dot_off")
        item(sep, 0, "")
        item(win32con.MF_STRING, _ID_OPEN, "Open Configuration", "open")
        item(sep, 0, "")
        if running:
            item(win32con.MF_STRING, _ID_STOP, "Stop Service", "stop")
        else:
            item(win32con.MF_STRING, _ID_START, "Start Service", "start")
        item(run_flag, _ID_RESTART_SVC, "Restart Service", "restart")
        item(sep, 0, "")
        item(win32con.MF_STRING, _ID_CHECK_UPDATE, "Check for updates", "update")
        item(win32con.MF_STRING, _ID_RESTART_APP, "Restart", "reboot")
        item(sep, 0, "")
        item(win32con.MF_STRING, _ID_QUIT, "Quit", "quit")

        x, y = win32api.GetCursorPos()
        # Required so the menu dismisses correctly when clicking elsewhere.
        win32gui.SetForegroundWindow(self._hwnd)
        cmd = win32gui.TrackPopupMenu(
            menu,
            win32con.TPM_RIGHTBUTTON | win32con.TPM_RETURNCMD | win32con.TPM_NONOTIFY,
            x, y, 0, self._hwnd, None,
        )
        win32gui.PostMessage(self._hwnd, win32con.WM_NULL, 0, 0)
        win32gui.DestroyMenu(menu)
        action = _CMD_TO_ACTION.get(cmd)
        if action:
            self._safe(self._actions.get(action))

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == _WM_TRAY:
            if lparam in (win32con.WM_LBUTTONUP, win32con.WM_LBUTTONDBLCLK):
                self._safe(self._on_left)
            elif lparam in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
                self._show_menu()
            return 0
        if msg == _WM_SHOW:  # a second instance asked us to surface the window
            self._safe(self._on_left)
            return 0
        if msg == _WM_DO_ADD:
            if not self._visible:
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_ADD, self._nid())
                    self._visible = True
                except Exception:
                    pass
            return 0
        if msg == _WM_DO_DELETE:
            if self._visible:
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self._hwnd, 0))
                except Exception:
                    pass
                self._visible = False
            return 0
        if msg == _WM_DO_TIP:
            if self._visible:
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_MODIFY, self._nid())
                except Exception:
                    pass
            return 0
        if msg == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        if msg == win32con.WM_DESTROY:
            if self._visible:
                try:
                    win32gui.Shell_NotifyIcon(win32gui.NIM_DELETE, (self._hwnd, 0))
                except Exception:
                    pass
                self._visible = False
            win32gui.PostQuitMessage(0)
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)
