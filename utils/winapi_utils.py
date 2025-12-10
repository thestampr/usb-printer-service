"""Utility helpers for controlling Windows desktop windows via Win32 APIs.

This module extracts the practical pieces from the hPyT package and omits
showcase effects such as rainbow animations. The functions here focus on tasks
that are typically useful for real applications, like hiding system chrome,
adjusting window frames, or syncing title and border colors.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import platform
import threading
import time
from typing import Any, Dict, List, Tuple, Union
from enum import Enum

try:
    from ctypes.wintypes import HWND, RECT, UINT
    import winreg
except ImportError as exc:  # pragma: no cover - Windows only
    raise ImportError("Windows API utilities require a Windows environment") from exc

set_window_pos = ctypes.windll.user32.SetWindowPos

if platform.architecture()[0] == "64bit":
    set_window_long = ctypes.windll.user32.SetWindowLongPtrW
    get_window_long = ctypes.windll.user32.GetWindowLongPtrW
else:  # pragma: no cover - 32-bit fallback
    set_window_long = ctypes.windll.user32.SetWindowLongW
    get_window_long = ctypes.windll.user32.GetWindowLongW

call_window_proc = ctypes.windll.user32.CallWindowProcW
flash_window_ex = ctypes.windll.user32.FlashWindowEx

_LRESULT = (
    ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
)

GWL_STYLE = -16
GWL_EXSTYLE = -20
GWL_WNDPROC = -4

WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_BORDER = 0x00800000
WS_EX_LAYERED = 0x00080000

WM_NCCALCSIZE = 0x0083
WM_NCHITTEST = 0x0084
WM_NCACTIVATE = 0x0086
WM_NCPAINT = 0x0085

SWP_NOZORDER = 0x0004
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_FRAMECHANGED = 0x0020

LWA_ALPHA = 0x0002

FLASHW_STOP = 0
FLASHW_CAPTION = 1
FLASHW_TRAY = 2
FLASHW_ALL = 3
FLASHW_TIMER = 4
FLASHW_TIMERNOFG = 12

accent_color_titlebars: List[int] = []
accent_color_borders: List[int] = []

WINDOWS_VERSION = float(platform.version().split(".")[0])


class CornerStyle(Enum):
    SQUARE = 1
    ROUND = 2
    ROUND_SMALL = 3


class FLASHWINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint),
        ("hwnd", ctypes.c_void_p),
        ("dwFlags", ctypes.c_uint),
        ("uCount", ctypes.c_uint),
        ("dwTimeout", ctypes.c_uint),
    ]


class PWINDOWPOS(ctypes.Structure):
    _fields_ = [
        ("hWnd", HWND),
        ("hwndInsertAfter", HWND),
        ("x", ctypes.c_int),
        ("y", ctypes.c_int),
        ("cx", ctypes.c_int),
        ("cy", ctypes.c_int),
        ("flags", UINT),
    ]


class NCCALCSIZE_PARAMS(ctypes.Structure):
    _fields_ = [("rgrc", RECT * 3), ("lppos", ctypes.POINTER(PWINDOWPOS))]


class TitleBar:
    """Hide or restore a window's system title bar and borders."""

    _height_reduction: Dict[int, int] = {}
    _old_wndproc: Dict[int, int] = {}
    _custom_wndproc: Dict[int, ctypes.WINFUNCTYPE] = {}
    _WNDPROC = ctypes.WINFUNCTYPE(
        _LRESULT,
        ctypes.c_void_p,
        ctypes.c_uint,
        ctypes.c_void_p,
        ctypes.c_void_p,
    )

    @classmethod
    def _install_wndproc(cls, hwnd: int, border_width: int) -> None:
        if hwnd in cls._custom_wndproc or WINDOWS_VERSION < 10.0:
            return

        old_proc = cls._old_wndproc.setdefault(
            hwnd, get_window_long(hwnd, GWL_WNDPROC)
        )

        def handler(h_wnd, msg, w_param, l_param):
            if msg == WM_NCCALCSIZE and w_param:
                params = NCCALCSIZE_PARAMS.from_address(l_param)
                params.rgrc[0].top -= border_width
            elif msg in (WM_NCACTIVATE, WM_NCPAINT):
                return 1
            return call_window_proc(
                ctypes.c_void_p(old_proc), h_wnd, msg, w_param, l_param
            )

        proc = cls._WNDPROC(handler)
        cls._custom_wndproc[hwnd] = proc
        set_window_long(hwnd, GWL_WNDPROC, proc)

    @classmethod
    def hide(cls, window: Any, no_span: bool = False) -> None:
        hwnd = module_find(window)

        rect = RECT()
        client_rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        ctypes.windll.user32.GetClientRect(hwnd, ctypes.byref(client_rect))

        full_width = rect.right - rect.left
        full_height = rect.bottom - rect.top
        client_width = client_rect.right
        client_height = client_rect.bottom

        border_width = (full_width - client_width) // 2
        title_bar_height = full_height - client_height - border_width

        if hwnd not in cls._old_wndproc:
            cls._old_wndproc[hwnd] = get_window_long(hwnd, GWL_WNDPROC)
        cls._install_wndproc(hwnd, border_width)

        old_style = get_window_long(hwnd, GWL_STYLE)
        new_style = (old_style & ~WS_CAPTION) | WS_BORDER
        set_window_long(hwnd, GWL_STYLE, new_style)

        if no_span:
            cls._height_reduction[hwnd] = title_bar_height
            set_window_pos(
                hwnd,
                0,
                0,
                0,
                full_width,
                full_height - title_bar_height,
                SWP_NOZORDER | SWP_NOMOVE,
            )
        else:
            set_window_pos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )

    @classmethod
    def unhide(cls, window: Any) -> None:
        hwnd = module_find(window)

        if hwnd in cls._custom_wndproc:
            old_proc = cls._old_wndproc.get(hwnd)
            if old_proc is not None:
                set_window_long(hwnd, GWL_WNDPROC, old_proc)
            del cls._custom_wndproc[hwnd]

        height_reduction = cls._height_reduction.pop(hwnd, 0)

        old_style = get_window_long(hwnd, GWL_STYLE)
        new_style = old_style | WS_CAPTION
        set_window_long(hwnd, GWL_STYLE, new_style)

        if height_reduction:
            rect = RECT()
            ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
            set_window_pos(
                hwnd,
                0,
                0,
                0,
                rect.right - rect.left,
                rect.bottom - rect.top + height_reduction,
                SWP_NOZORDER | SWP_NOMOVE,
            )
        else:
            set_window_pos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
            )


class MaximizeMinimizeButton:
    """Hide or reveal both the maximize and minimize buttons."""

    @staticmethod
    def hide(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style & ~WS_MAXIMIZEBOX & ~WS_MINIMIZEBOX)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )

    @staticmethod
    def unhide(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style | WS_MAXIMIZEBOX | WS_MINIMIZEBOX)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )


class MaximizeButton:
    """Toggle the maximize button independently."""

    @staticmethod
    def disable(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style & ~WS_MAXIMIZEBOX)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )

    @staticmethod
    def enable(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style | WS_MAXIMIZEBOX)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )


class MinimizeButton:
    """Toggle the minimize button independently."""

    @staticmethod
    def disable(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style & ~WS_MINIMIZEBOX)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )

    @staticmethod
    def enable(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style | WS_MINIMIZEBOX)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )


class SystemMenu:
    """Hide or restore the entire system menu (icon + buttons)."""

    @staticmethod
    def hide(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style & ~WS_SYSMENU)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )

    @staticmethod
    def unhide(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_STYLE)
        set_window_long(hwnd, GWL_STYLE, style | WS_SYSMENU)
        set_window_pos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED,
        )


class WindowFlash:
    """Trigger the built-in Windows flash animation on the taskbar and caption."""

    @staticmethod
    def flash(window: Any, count: int = 5, interval_ms: int = 1000) -> None:
        hwnd = module_find(window)
        info = FLASHWINFO(
            cbSize=ctypes.sizeof(FLASHWINFO),
            hwnd=hwnd,
            dwFlags=FLASHW_ALL | FLASHW_TIMER,
            uCount=count,
            dwTimeout=interval_ms,
        )
        flash_window_ex(ctypes.pointer(info))

    @staticmethod
    def stop(window: Any) -> None:
        hwnd = module_find(window)
        info = FLASHWINFO(
            cbSize=ctypes.sizeof(FLASHWINFO),
            hwnd=hwnd,
            dwFlags=FLASHW_STOP,
            uCount=0,
            dwTimeout=0,
        )
        flash_window_ex(ctypes.pointer(info))


class Opacity:
    """Set per-window opacity."""

    @staticmethod
    def set(window: Any, opacity: Union[int, float]) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)

        if isinstance(opacity, float) and 0.0 <= opacity <= 1.0:
            alpha = int(opacity * 255)
        elif isinstance(opacity, int) and 0 <= opacity <= 255:
            alpha = opacity
        else:
            raise ValueError("Opacity must be 0-255 or a float between 0.0 and 1.0")

        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, alpha, LWA_ALPHA)


class TitleBarColor:
    """Control title bar colors without any showcase effects."""

    @staticmethod
    def set(window: Any, color: Union[Tuple[int, int, int], str]) -> None:
        hwnd = module_find(window)
        converted = convert_color(color)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(ctypes.c_int(converted)), 4
        )
        set_window_long(hwnd, GWL_EXSTYLE, style)

    @staticmethod
    def set_accent(window: Any) -> None:
        hwnd = module_find(window)
        if hwnd in accent_color_titlebars:
            raise RuntimeError("Accent tracking already active for this window")

        accent_color_titlebars.append(hwnd)

        def updater() -> None:
            last_color = ""
            while hwnd in accent_color_titlebars:
                accent = get_accent_color()
                if accent != last_color:
                    TitleBarColor.set(window, accent)
                    last_color = accent
                time.sleep(1)

        thread = threading.Thread(target=updater, daemon=True)
        thread.start()

    @staticmethod
    def reset(window: Any) -> None:
        hwnd = module_find(window)
        if hwnd in accent_color_titlebars:
            accent_color_titlebars.remove(hwnd)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 35, ctypes.byref(ctypes.c_int(-1)), 4
        )
        set_window_long(hwnd, GWL_EXSTYLE, style)


class TitleBarTextColor:
    """Control the foreground (text/icon) color in the title bar."""

    @staticmethod
    def set(window: Any, color: Union[Tuple[int, int, int], str]) -> None:
        hwnd = module_find(window)
        converted = convert_color(color)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(ctypes.c_int(converted)), 4
        )
        set_window_long(hwnd, GWL_EXSTYLE, style)

    @staticmethod
    def reset(window: Any) -> None:
        hwnd = module_find(window)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 36, ctypes.byref(ctypes.c_int(-1)), 4
        )
        set_window_long(hwnd, GWL_EXSTYLE, style)


class BorderColor:
    """Control the border accent color without rainbow effects."""

    @staticmethod
    def set(window: Any, color: Union[Tuple[int, int, int], str]) -> None:
        hwnd = module_find(window)
        converted = convert_color(color)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 34, ctypes.byref(ctypes.c_int(converted)), 4
        )
        set_window_long(hwnd, GWL_EXSTYLE, style)

    @staticmethod
    def set_accent(window: Any) -> None:
        hwnd = module_find(window)
        if hwnd in accent_color_borders:
            raise RuntimeError("Accent tracking already active for this window")

        accent_color_borders.append(hwnd)

        def updater() -> None:
            last_color = ""
            while hwnd in accent_color_borders:
                accent = get_accent_color()
                if accent != last_color:
                    BorderColor.set(window, accent)
                    last_color = accent
                time.sleep(1)

        thread = threading.Thread(target=updater, daemon=True)
        thread.start()

    @staticmethod
    def reset(window: Any) -> None:
        hwnd = module_find(window)
        if hwnd in accent_color_borders:
            accent_color_borders.remove(hwnd)
        style = get_window_long(hwnd, GWL_EXSTYLE)
        set_window_long(hwnd, GWL_EXSTYLE, style | WS_EX_LAYERED)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 34, ctypes.byref(ctypes.c_int(-1)), 4
        )
        set_window_long(hwnd, GWL_EXSTYLE, style)


class WindowFrame:
    """Move, resize, and center windows."""

    @staticmethod
    def center(window: Any) -> None:
        hwnd = module_find(window)

        rect = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        screen_width = ctypes.windll.user32.GetSystemMetrics(0)
        screen_height = ctypes.windll.user32.GetSystemMetrics(1)

        new_x = (screen_width - width) // 2
        new_y = (screen_height - height) // 2

        set_window_pos(hwnd, 0, new_x, new_y, 0, 0, SWP_NOSIZE | SWP_NOZORDER)

    @staticmethod
    def center_relative(parent: Any, child: Any) -> None:
        hwnd_parent = module_find(parent)
        hwnd_child = module_find(child)

        rect_parent = RECT()
        rect_child = RECT()
        ctypes.windll.user32.GetWindowRect(hwnd_parent, ctypes.byref(rect_parent))
        ctypes.windll.user32.GetWindowRect(hwnd_child, ctypes.byref(rect_child))

        parent_width = rect_parent.right - rect_parent.left
        parent_height = rect_parent.bottom - rect_parent.top
        child_width = rect_child.right - rect_child.left
        child_height = rect_child.bottom - rect_child.top

        new_x = rect_parent.left + (parent_width - child_width) // 2
        new_y = rect_parent.top + (parent_height - child_height) // 2

        set_window_pos(hwnd_child, 0, new_x, new_y, 0, 0, SWP_NOSIZE | SWP_NOZORDER)

    @staticmethod
    def move(window: Any, x: int, y: int) -> None:
        hwnd = module_find(window)
        set_window_pos(hwnd, 0, x, y, 0, 0, SWP_NOSIZE | SWP_NOZORDER)

    @staticmethod
    def resize(window: Any, width: int, height: int) -> None:
        hwnd = module_find(window)
        set_window_pos(hwnd, 0, 0, 0, width, height, SWP_NOMOVE | SWP_NOZORDER)

    @staticmethod
    def minimize(window: Any) -> None:
        hwnd = module_find(window)
        ctypes.windll.user32.ShowWindow(hwnd, 6)

    @staticmethod
    def maximize(window: Any) -> None:
        hwnd = module_find(window)
        ctypes.windll.user32.ShowWindow(hwnd, 3)

    @staticmethod
    def restore(window: Any) -> None:
        hwnd = module_find(window)
        ctypes.windll.user32.ShowWindow(hwnd, 9)

    @staticmethod
    def foreground(window: Any) -> None:
        hwnd = module_find(window)
        ctypes.windll.user32.SetForegroundWindow(hwnd)


class CornerRadius:
    """Control rounded corner preferences on Windows 11+."""

    @staticmethod
    def set(window: Any, style: CornerStyle = CornerStyle.ROUND) -> None:
        if WINDOWS_VERSION < 11.0:
            raise RuntimeError("Corner radius control requires Windows 11 or later")
        
        if not isinstance(style, CornerStyle):
            raise ValueError('Style must be an instance of CornerStyle Enum')

        hwnd = module_find(window)
        value = ctypes.c_int(style.value)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), 4)

    @staticmethod
    def reset(window: Any) -> None:
        hwnd = module_find(window)
        value = ctypes.c_int(0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(value), 4)


class WindowDWM:
    """Expose a few useful Desktop Window Manager toggles."""

    @staticmethod
    def toggle_transitions(window: Any, enabled: bool = True) -> None:
        hwnd = module_find(window)
        value = ctypes.c_int(0 if enabled else 1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 3, ctypes.byref(value), 4)

    @staticmethod
    def toggle_rtl_layout(window: Any, enabled: bool = True) -> None:
        hwnd = module_find(window)
        value = ctypes.c_int(1 if enabled else 0)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 6, ctypes.byref(value), 4)

    @staticmethod
    def toggle_cloak(window: Any, enabled: bool = True) -> None:
        hwnd = module_find(window)
        value = ctypes.wintypes.BOOL(enabled)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, 13, ctypes.byref(value), ctypes.sizeof(value)
        )


class TitleText:
    """Minimal helpers for setting and restoring window titles."""

    _original_titles: Dict[int, str] = {}

    @staticmethod
    def set(window: Any, title: str) -> None:
        hwnd = module_find(window)
        if hwnd not in TitleText._original_titles:
            TitleText._original_titles[hwnd] = _get_window_text(hwnd)
        ctypes.windll.user32.SetWindowTextW(hwnd, title)

    @staticmethod
    def reset(window: Any) -> None:
        hwnd = module_find(window)
        original = TitleText._original_titles.pop(hwnd, None)
        if original is not None:
            ctypes.windll.user32.SetWindowTextW(hwnd, original)


def convert_color(color: Union[Tuple[int, int, int], str]) -> int:
    if isinstance(color, tuple) and len(color) == 3:
        r, g, b = color
    elif isinstance(color, str) and color.startswith("#") and len(color) == 7:
        r = int(color[1:3], 16)
        g = int(color[3:5], 16)
        b = int(color[5:7], 16)
    else:
        raise ValueError("Color must be an RGB tuple or #RRGGBB string")
    return (b << 16) | (g << 8) | r


def get_accent_color() -> str:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\\Microsoft\\Windows\\DWM")
    value, _ = winreg.QueryValueEx(key, "ColorizationAfterglow")
    winreg.CloseKey(key)
    hex_value = hex(value)
    trimmed = hex_value[4:] if len(hex_value[4:]) == 6 else hex_value[2:]
    return f"#{trimmed}"


def module_find(window: Any) -> int:
    try:
        window.update()
        return ctypes.windll.user32.GetParent(window.winfo_id())
    except Exception:
        pass
    try:
        return window.winId().__int__()
    except Exception:
        pass
    try:
        return window.GetHandle()
    except Exception:
        pass
    try:
        gdk_window = window.get_window()
        return gdk_window.get_xid()
    except Exception:
        pass
    try:
        return window.root_window.get_window_info().window
    except Exception:
        pass
    return window


def get_window_from_title(title: str) -> int:
    hwnd = ctypes.windll.user32.FindWindowW(None, title)
    if hwnd == 0:
        raise ValueError(f'No window found with title: "{title}"')
    return hwnd


def _get_window_text(hwnd: int) -> str:
    buffer = ctypes.create_unicode_buffer(1024)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, 1024)
    return buffer.value


__all__ = [
    "TitleBar",
    "MaximizeMinimizeButton",
    "MaximizeButton",
    "MinimizeButton",
    "SystemMenu",
    "WindowFlash",
    "Opacity",
    "TitleBarColor",
    "TitleBarTextColor",
    "BorderColor",
    "WindowFrame",
    "CornerRadius",
    "WindowDWM",
    "TitleText",
    "convert_color",
    "get_accent_color",
    "module_find",
    "get_window_from_title",
]
