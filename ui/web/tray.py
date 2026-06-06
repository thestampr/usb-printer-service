"""Windows system-tray icon + a custom Docker-style popup menu.

The icon runs on its own thread with a hidden message window; ``Shell_NotifyIcon``
must be called from that thread, so external calls are marshaled in via ``PostMessage``.

The right-click menu is a borderless, owner-drawn native popup window we paint
ourselves (not a webview / in-app window). A real ``TrackPopupMenu`` can't match
Docker's look because owner-drawn items force the classic light-bordered frame.
"""

from __future__ import annotations

import ctypes
import math
import threading
from ctypes import wintypes
from typing import Callable, Dict, List, Optional

import win32api
import win32con
import win32gui

_TRAY_CLASS = "PrinterServiceTrayWnd"
_MENU_CLASS = "PrinterServiceMenuWnd"

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

# --- Win32 message / style / flag constants we reference by hand -------------
_WM_PAINT = 0x000F
_WM_ERASEBKGND = 0x0014
_WM_MOUSEMOVE = 0x0200
_WM_LBUTTONUP = 0x0202
_WM_RBUTTONUP = 0x0205
_WM_MOUSELEAVE = 0x02A3
_WM_MOUSEACTIVATE = 0x0021
_WM_SETCURSOR = 0x0020

_MA_NOACTIVATE = 3   # clicking the menu must NOT activate it (keeps overflow open)
_TME_LEAVE = 0x00000002
_VK_LBUTTON = 0x01
_VK_RBUTTON = 0x02
_VK_ESCAPE = 0x1B

_WS_POPUP = 0x80000000
_WS_EX_TOOLWINDOW = 0x00000080
_WS_EX_TOPMOST = 0x00000008
_WS_EX_LAYERED = 0x00080000   # so we can fade the menu in via a constant alpha
_LWA_ALPHA = 0x00000002
_CS_DROPSHADOW = 0x00020000
_HWND_TOPMOST = -1
_SWP_NOACTIVATE = 0x0010
_SWP_SHOWWINDOW = 0x0040
_SRCCOPY = 0x00CC0020
_IDC_ARROW = 32512
_MONITOR_DEFAULTTONEAREST = 2

# Rounded corners + no border on our own popup window (Docker has no border).
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWCP_ROUND = 2
_DWMWA_COLOR_NONE = 0xFFFFFFFE

# DrawText flags.
_DT_LEFT = 0x0000
_DT_SINGLELINE = 0x0020
_DT_VCENTER = 0x0004
_DT_NOPREFIX = 0x0800

# Docker-style palette (sampled from Docker Desktop's tray menu).
_C_BG = (31, 31, 31)         # menu background  #1F1F1F
_C_HOVER = (54, 54, 56)      # row hover/selection
_C_TEXT = (227, 227, 227)    # normal item text #E3E3E3
_C_HEADER = (154, 160, 166)  # status-header text #9AA0A6
_C_DISABLED = (110, 110, 114)  # grayed item text
_C_SEP = (94, 94, 94)        # divider line #5E5E5E
_C_DOT_ON = (55, 205, 82)    # running status dot (Docker green #37CD52)
_C_DOT_OFF = (124, 128, 138)  # stopped status dot
_C_ICON = (214, 214, 214)    # item glyph (e.g. Quit power)

# Layout metrics at 96 DPI (scaled by the popup's DPI at menu time).
_ROW_H = 30
_HEADER_H = 35
_SEP_H = 17       # separator row height; the line sits centered, so this is its margin
_PAD_L = 14       # left padding to the icon gutter
_ICON = 14        # icon gutter width (px); icons are drawn as vectors within it
_TEXT_GAP = 12    # gap between the icon gutter and text
_PAD_R = 24       # right padding
_PAD_V = 10       # top/bottom padding inside the rounded body
_MIN_W = 200      # minimum menu width
_FONT_PT = 9


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _SIZE(ctypes.Structure):
    _fields_ = [("cx", wintypes.LONG), ("cy", wintypes.LONG)]


class _TRACKMOUSEEVENT(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("hwndTrack", wintypes.HWND), ("dwHoverTime", wintypes.DWORD)]


class _GpPointF(ctypes.Structure):
    _fields_ = [("X", ctypes.c_float), ("Y", ctypes.c_float)]


_gdi_ready = False


def _init_gdi() -> None:
    """Pin ctypes prototypes for the GDI/user calls (so x64 handles aren't truncated)."""
    global _gdi_ready
    if _gdi_ready:
        return
    cvp, ci, dw, cu = ctypes.c_void_p, ctypes.c_int, wintypes.DWORD, ctypes.c_uint
    g, u = ctypes.windll.gdi32, ctypes.windll.user32
    g.CreateSolidBrush.restype = cvp; g.CreateSolidBrush.argtypes = [dw]
    g.CreateFontW.restype = cvp
    g.CreateFontW.argtypes = [ci] * 5 + [dw] * 8 + [wintypes.LPCWSTR]
    g.SelectObject.restype = cvp; g.SelectObject.argtypes = [cvp, cvp]
    g.DeleteObject.argtypes = [cvp]
    g.CreateCompatibleDC.restype = cvp; g.CreateCompatibleDC.argtypes = [cvp]
    g.CreateCompatibleBitmap.restype = cvp; g.CreateCompatibleBitmap.argtypes = [cvp, ci, ci]
    g.DeleteDC.argtypes = [cvp]
    g.BitBlt.argtypes = [cvp, ci, ci, ci, ci, cvp, ci, ci, dw]; g.BitBlt.restype = wintypes.BOOL
    g.SetTextColor.argtypes = [cvp, dw]; g.SetTextColor.restype = dw
    g.SetBkMode.argtypes = [cvp, ci]
    g.GetTextExtentPoint32W.argtypes = [cvp, wintypes.LPCWSTR, ci, cvp]
    g.GetTextExtentPoint32W.restype = wintypes.BOOL
    u.FillRect.argtypes = [cvp, cvp, cvp]; u.FillRect.restype = ci
    u.DrawTextW.argtypes = [cvp, wintypes.LPCWSTR, ci, cvp, cu]; u.DrawTextW.restype = ci
    u.GetDC.restype = cvp; u.GetDC.argtypes = [cvp]
    u.ReleaseDC.argtypes = [cvp, cvp]
    u.PeekMessageW.argtypes = [cvp, cvp, cu, cu, cu]; u.PeekMessageW.restype = ci
    u.TranslateMessage.argtypes = [cvp]
    u.DispatchMessageW.argtypes = [cvp]
    u.SetLayeredWindowAttributes.argtypes = [cvp, dw, ctypes.c_ubyte, dw]
    try:
        u.GetDpiForWindow.restype = cu; u.GetDpiForWindow.argtypes = [cvp]
    except Exception:
        pass
    _gdi_ready = True


def _rgb(c) -> int:
    """(r, g, b) -> Win32 COLORREF (0x00BBGGRR)."""
    return c[0] | (c[1] << 8) | (c[2] << 16)


_gdiplus_token = None
_gdiplus_draw_ready = False

# GDI+ enums.
_SMOOTHING_ANTIALIAS = 4
_UNIT_PIXEL = 2
_LINECAP_ROUND = 2


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


def _gdiplus_draw_init() -> bool:
    """Pin ctypes prototypes for the GDI+ vector-drawing calls (floats + handles)."""
    global _gdiplus_draw_ready
    if _gdiplus_draw_ready:
        return True
    if not _gdiplus_start():
        return False
    cvp, cf, ci, cu = ctypes.c_void_p, ctypes.c_float, ctypes.c_int, ctypes.c_uint
    pp = ctypes.POINTER(ctypes.c_void_p)
    g = ctypes.windll.gdiplus
    g.GdipCreateFromHDC.argtypes = [cvp, pp]
    g.GdipDeleteGraphics.argtypes = [cvp]
    g.GdipSetSmoothingMode.argtypes = [cvp, ci]
    g.GdipCreateSolidFill.argtypes = [cu, pp]
    g.GdipDeleteBrush.argtypes = [cvp]
    g.GdipFillEllipse.argtypes = [cvp, cvp, cf, cf, cf, cf]
    g.GdipFillRectangle.argtypes = [cvp, cvp, cf, cf, cf, cf]
    g.GdipFillPolygon.argtypes = [cvp, cvp, ctypes.POINTER(_GpPointF), ci, ci]
    g.GdipCreatePen1.argtypes = [cu, cf, ci, pp]
    g.GdipDeletePen.argtypes = [cvp]
    g.GdipSetPenStartCap.argtypes = [cvp, ci]
    g.GdipSetPenEndCap.argtypes = [cvp, ci]
    g.GdipDrawArc.argtypes = [cvp, cvp, cf, cf, cf, cf, cf, cf]
    g.GdipDrawLine.argtypes = [cvp, cvp, cf, cf, cf, cf]
    _gdiplus_draw_ready = True
    return True


def _argb(c, a=255) -> int:
    """(r, g, b) -> GDI+ ARGB (0xAARRGGBB)."""
    return (a << 24) | (c[0] << 16) | (c[1] << 8) | c[2]


class Tray:
    """A single tray icon with a custom Docker-style popup menu. Callbacks run on
    the tray thread; ``actions`` maps "open"/"start"/"stop"/"restart"/
    "check_update"/"restart_app"/"quit" to callables and ``state_provider``
    returns ``{running, host, port}`` for the menu's status header."""

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
        self._hinst = None
        self._hicon = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._visible = False
        self._menu_class_ok = False
        self._arrow_cursor = None
        # Owner-draw resources (created lazily on the tray thread).
        self._dpi = 96
        self._font = None
        self._font_dpi = 0
        self._brushes: Dict[str, int] = {}
        # Live popup-menu state (single menu at a time, tray thread).
        self._menu_hwnd: Optional[int] = None
        self._menu_rows: List[dict] = []
        self._menu_w = 0
        self._menu_h = 0
        self._menu_hover = -1
        self._menu_result: Optional[int] = None
        self._menu_done = True

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
        self._hinst = win32gui.GetModuleHandle(None)
        wc = win32gui.WNDCLASS()
        wc.hInstance = self._hinst
        wc.lpszClassName = _TRAY_CLASS
        wc.lpfnWndProc = self._wndproc
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error:
            pass  # already registered in this process
        self._hwnd = win32gui.CreateWindow(
            wc.lpszClassName, "PrinterServiceTray", 0, 0, 0, 0, 0, 0, 0, self._hinst, None
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

    # -- vector icons (drawn with GDI+, crisp at any DPI) ----------------

    def _draw_dot(self, hdc, cx, cy, diam, color) -> None:
        if not _gdiplus_draw_init():
            return
        g = ctypes.windll.gdiplus
        graphics = ctypes.c_void_p()
        if g.GdipCreateFromHDC(hdc, ctypes.byref(graphics)) != 0:
            return
        try:
            g.GdipSetSmoothingMode(graphics, _SMOOTHING_ANTIALIAS)
            brush = ctypes.c_void_p()
            g.GdipCreateSolidFill(_argb(color), ctypes.byref(brush))
            r = diam / 2.0
            g.GdipFillEllipse(graphics, brush, ctypes.c_float(cx - r),
                              ctypes.c_float(cy - r), ctypes.c_float(diam), ctypes.c_float(diam))
            g.GdipDeleteBrush(brush)
        finally:
            g.GdipDeleteGraphics(graphics)

    def _draw_power(self, hdc, cx, cy, size, color) -> None:
        """Power glyph: a ring with a gap at the top + a vertical stem."""
        if not _gdiplus_draw_init():
            return
        g = ctypes.windll.gdiplus
        graphics = ctypes.c_void_p()
        if g.GdipCreateFromHDC(hdc, ctypes.byref(graphics)) != 0:
            return
        try:
            g.GdipSetSmoothingMode(graphics, _SMOOTHING_ANTIALIAS)
            width = max(1.4, size * 0.11)
            pen = ctypes.c_void_p()
            g.GdipCreatePen1(_argb(color), ctypes.c_float(width), _UNIT_PIXEL, ctypes.byref(pen))
            g.GdipSetPenStartCap(pen, _LINECAP_ROUND)
            g.GdipSetPenEndCap(pen, _LINECAP_ROUND)
            r = size * 0.36
            top = cy - r + size * 0.06  # nudge ring down so the stem clears it
            cf = ctypes.c_float
            # Arc: leave ~70 deg gap centered at the top (top = -90 deg).
            g.GdipDrawArc(graphics, pen, cf(cx - r), cf(top), cf(2 * r), cf(2 * r),
                          cf(-55.0), cf(290.0))
            # Vertical stem from above the ring down to its centre.
            g.GdipDrawLine(graphics, pen, cf(cx), cf(cy - r - size * 0.06),
                           cf(cx), cf(cy + size * 0.02))
            g.GdipDeletePen(pen)
        finally:
            g.GdipDeleteGraphics(graphics)

    def _gp(self, hdc):
        """Create an antialiased GDI+ Graphics for hdc (caller deletes it)."""
        g = ctypes.windll.gdiplus
        graphics = ctypes.c_void_p()
        if g.GdipCreateFromHDC(hdc, ctypes.byref(graphics)) != 0:
            return None
        g.GdipSetSmoothingMode(graphics, _SMOOTHING_ANTIALIAS)
        return graphics

    def _draw_play(self, hdc, cx, cy, size, color) -> None:
        """Right-pointing filled triangle (Start)."""
        if not _gdiplus_draw_init():
            return
        g = ctypes.windll.gdiplus
        graphics = self._gp(hdc)
        if not graphics:
            return
        try:
            brush = ctypes.c_void_p()
            g.GdipCreateSolidFill(_argb(color), ctypes.byref(brush))
            w, h = size * 0.82, size * 0.96
            x0 = cx - w / 2 + size * 0.07  # nudge right so it reads optically centered
            pts = (_GpPointF * 3)(_GpPointF(x0, cy - h / 2),
                                  _GpPointF(x0, cy + h / 2),
                                  _GpPointF(x0 + w, cy))
            g.GdipFillPolygon(graphics, brush, pts, 3, 0)
            g.GdipDeleteBrush(brush)
        finally:
            g.GdipDeleteGraphics(graphics)

    def _draw_stop(self, hdc, cx, cy, size, color) -> None:
        """Filled square (Stop)."""
        if not _gdiplus_draw_init():
            return
        g = ctypes.windll.gdiplus
        graphics = self._gp(hdc)
        if not graphics:
            return
        try:
            brush = ctypes.c_void_p()
            g.GdipCreateSolidFill(_argb(color), ctypes.byref(brush))
            g.GdipFillRectangle(graphics, brush, cx - size / 2, cy - size / 2, size, size)
            g.GdipDeleteBrush(brush)
        finally:
            g.GdipDeleteGraphics(graphics)

    def _draw_restart(self, hdc, cx, cy, size, color) -> None:
        """Circular arrow (Restart): an arc with a gap + an arrowhead."""
        if not _gdiplus_draw_init():
            return
        g = ctypes.windll.gdiplus
        graphics = self._gp(hdc)
        if not graphics:
            return
        try:
            width = max(1.4, size * 0.12)
            pen = ctypes.c_void_p()
            g.GdipCreatePen1(_argb(color), width, _UNIT_PIXEL, ctypes.byref(pen))
            g.GdipSetPenStartCap(pen, _LINECAP_ROUND)
            r = size * 0.36
            start, sweep = 300.0, 300.0  # 60deg gap centered at the top
            g.GdipDrawArc(graphics, pen, cx - r, cy - r, 2 * r, 2 * r, start, sweep)
            g.GdipDeletePen(pen)
            # Arrowhead at the leading (end) of the clockwise arc.
            a = math.radians(start + sweep)
            px, py = cx + r * math.cos(a), cy + r * math.sin(a)
            tx, ty = -math.sin(a), math.cos(a)   # clockwise tangent
            nx, ny = math.cos(a), math.sin(a)    # radial
            al, aw = size * 0.40, size * 0.40
            brush = ctypes.c_void_p()
            g.GdipCreateSolidFill(_argb(color), ctypes.byref(brush))
            pts = (_GpPointF * 3)(
                _GpPointF(px + tx * al, py + ty * al),
                _GpPointF(px + nx * aw / 2, py + ny * aw / 2),
                _GpPointF(px - nx * aw / 2, py - ny * aw / 2))
            g.GdipFillPolygon(graphics, brush, pts, 3, 0)
            g.GdipDeleteBrush(brush)
        finally:
            g.GdipDeleteGraphics(graphics)

    # -- drawing resources & math ----------------------------------------

    def _scale(self, v) -> int:
        return int(round(v * self._dpi / 96.0))

    def _ensure_resources(self) -> None:
        """Create the font (for current DPI) + solid brushes. Tray thread."""
        _init_gdi()
        g = ctypes.windll.gdi32
        if self._font is None or self._font_dpi != self._dpi:
            if self._font:
                g.DeleteObject(self._font)
            height = -self._scale(_FONT_PT * 96 / 72)  # px height at this DPI
            self._font = g.CreateFontW(height, 0, 0, 0, 400, 0, 0, 0, 1, 0, 0, 5, 0, "Segoe UI")
            self._font_dpi = self._dpi
        if not self._brushes:
            for key, color in (("bg", _C_BG), ("hover", _C_HOVER), ("sep", _C_SEP)):
                self._brushes[key] = g.CreateSolidBrush(_rgb(color))

    def _text_width(self, text: str) -> int:
        u, g = ctypes.windll.user32, ctypes.windll.gdi32
        hdc = u.GetDC(self._menu_hwnd or self._hwnd)
        old = g.SelectObject(hdc, self._font)
        size = _SIZE()
        g.GetTextExtentPoint32W(hdc, text, len(text), ctypes.byref(size))
        g.SelectObject(hdc, old)
        u.ReleaseDC(self._menu_hwnd or self._hwnd, hdc)
        return int(size.cx)

    def _build_rows(self, running: bool) -> List[dict]:
        """Descriptors for the menu, in order (status header -> grouped sections)."""
        rows: List[dict] = []

        def item(cmd, text, kind="item", icon=None, enabled=True):
            rows.append({"cmd": cmd, "text": text, "kind": kind,
                         "icon": icon, "enabled": enabled})

        def sep():
            item(0, "", kind="sep", enabled=False)

        # Service rows + the status dot and Quit carry an icon; "Open Config" /
        # "Check for updates" don't, but the gutter is reserved so text lines up.
        item(0, "Service is running" if running else "Service is stopped",
             kind="header", icon="dot_on" if running else "dot_off", enabled=False)
        sep()
        item(_ID_OPEN, "Open Config")
        sep()
        if running:
            item(_ID_STOP, "Stop Service", icon="stop")
        else:
            item(_ID_START, "Start Service", icon="play")
        item(_ID_RESTART_SVC, "Restart Service", icon="restart", enabled=running)
        sep()
        item(_ID_CHECK_UPDATE, "Check for updates")
        item(_ID_RESTART_APP, "Restart")
        sep()
        item(_ID_QUIT, "Quit", icon="power")
        return rows

    def _layout(self, rows: List[dict]):
        """Assign each row a y-range and compute the menu's pixel size."""
        text_x = self._scale(_PAD_L + _ICON + _TEXT_GAP)
        width = self._scale(_MIN_W)
        for r in rows:
            if r["kind"] != "sep":
                width = max(width, text_x + self._text_width(r["text"]) + self._scale(_PAD_R))
        y = self._scale(_PAD_V)
        laid: List[dict] = []
        for i, r in enumerate(rows):
            if r["kind"] == "sep":
                h = self._scale(_SEP_H)
            elif r["kind"] == "header":
                h = self._scale(_HEADER_H)
            else:
                h = self._scale(_ROW_H)
            selectable = r["kind"] == "item" and r["enabled"]
            laid.append({**r, "idx": i, "top": y, "bottom": y + h, "selectable": selectable})
            y += h
        height = y + self._scale(_PAD_V)
        return laid, width, height

    # -- painting --------------------------------------------------------

    def _paint_row(self, hdc, row, selected: bool) -> None:
        g, u = ctypes.windll.gdi32, ctypes.windll.user32
        top, bottom, w = row["top"], row["bottom"], self._menu_w
        grayed = row["kind"] == "item" and not row["enabled"]

        if row["kind"] == "sep":
            mid = top + (bottom - top) // 2
            line = _RECT(0, mid, w, mid + 1)
            u.FillRect(hdc, ctypes.byref(line), self._brushes["sep"])
            return

        if selected:
            rc = _RECT(0, top, w, bottom)
            u.FillRect(hdc, ctypes.byref(rc), self._brushes["hover"])

        icon = row.get("icon")
        if icon:
            gutter = self._scale(_ICON)
            cx = self._scale(_PAD_L) + gutter / 2.0
            cy = (top + bottom) / 2.0
            glyph = _C_DISABLED if grayed else _C_ICON
            if icon == "dot_on":
                self._draw_dot(hdc, cx, cy, self._scale(9), _C_DOT_ON)
            elif icon == "dot_off":
                self._draw_dot(hdc, cx, cy, self._scale(9), _C_DOT_OFF)
            elif icon == "power":
                self._draw_power(hdc, cx, cy, self._scale(13), glyph)
            elif icon == "play":
                self._draw_play(hdc, cx, cy, self._scale(12), glyph)
            elif icon == "stop":
                self._draw_stop(hdc, cx, cy, self._scale(10), glyph)
            elif icon == "restart":
                self._draw_restart(hdc, cx, cy, self._scale(13), glyph)

        if row["kind"] == "header":
            color = _C_HEADER
        elif grayed:
            color = _C_DISABLED
        else:
            color = _C_TEXT
        g.SetBkMode(hdc, 1)  # TRANSPARENT
        g.SelectObject(hdc, self._font)
        g.SetTextColor(hdc, _rgb(color))
        tr = _RECT(self._scale(_PAD_L + _ICON + _TEXT_GAP), top,
                   w - self._scale(_PAD_R), bottom)
        u.DrawTextW(hdc, row["text"], len(row["text"]), ctypes.byref(tr),
                    _DT_LEFT | _DT_SINGLELINE | _DT_VCENTER | _DT_NOPREFIX)

    def _paint(self) -> None:
        g = ctypes.windll.gdi32
        u = ctypes.windll.user32
        hdc, ps = win32gui.BeginPaint(self._menu_hwnd)
        try:
            w, h = self._menu_w, self._menu_h
            mem = g.CreateCompatibleDC(hdc)
            bmp = g.CreateCompatibleBitmap(hdc, w, h)
            old = g.SelectObject(mem, bmp)
            u.FillRect(mem, ctypes.byref(_RECT(0, 0, w, h)), self._brushes["bg"])
            for row in self._menu_rows:
                self._paint_row(mem, row, selected=(row["idx"] == self._menu_hover))
            g.BitBlt(hdc, 0, 0, w, h, mem, 0, 0, _SRCCOPY)
            g.SelectObject(mem, old)
            g.DeleteObject(bmp)
            g.DeleteDC(mem)
        finally:
            win32gui.EndPaint(self._menu_hwnd, ps)

    # -- hit-testing & navigation ----------------------------------------

    @staticmethod
    def _xy(lparam):
        lparam &= 0xFFFFFFFF
        x = lparam & 0xFFFF
        y = (lparam >> 16) & 0xFFFF
        if x >= 0x8000:
            x -= 0x10000
        if y >= 0x8000:
            y -= 0x10000
        return x, y

    def _inside(self, x, y) -> bool:
        return 0 <= x < self._menu_w and 0 <= y < self._menu_h

    def _hit(self, x, y) -> int:
        if not self._inside(x, y):
            return -1
        for row in self._menu_rows:
            if row["selectable"] and row["top"] <= y < row["bottom"]:
                return row["idx"]
        return -1

    def _set_hover(self, idx: int) -> None:
        if idx != self._menu_hover:
            self._menu_hover = idx
            try:
                win32gui.InvalidateRect(self._menu_hwnd, None, False)
            except Exception:
                pass

    # -- the popup menu --------------------------------------------------

    def _ensure_menu_class(self) -> None:
        if self._menu_class_ok:
            return
        wc = win32gui.WNDCLASS()
        wc.hInstance = self._hinst
        wc.lpszClassName = _MENU_CLASS
        wc.lpfnWndProc = self._menu_wndproc
        wc.style = _CS_DROPSHADOW | win32con.CS_HREDRAW | win32con.CS_VREDRAW
        wc.hbrBackground = 0  # we paint everything
        try:
            self._arrow_cursor = win32gui.LoadCursor(0, _IDC_ARROW)
            wc.hCursor = self._arrow_cursor
        except Exception:
            pass
        try:
            win32gui.RegisterClass(wc)
        except win32gui.error:
            pass
        self._menu_class_ok = True

    def _place(self, px, py, w, h):
        """Position the menu near the cursor, flipped to stay on the work area."""
        x, y = px, py
        try:
            mon = win32api.MonitorFromPoint((px, py), _MONITOR_DEFAULTTONEAREST)
            wl, wt, wr, wb = win32api.GetMonitorInfo(mon)["Work"]
        except Exception:
            wl, wt, wr, wb = 0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
        if x + w > wr:
            x = max(wl, x - w)   # open to the left of the cursor
        if y + h > wb:
            y = max(wt, y - h)   # open above the cursor (typical for the tray)
        x = max(wl, min(x, wr - w))
        y = max(wt, min(y, wb - h))
        return x, y

    def _show_menu(self) -> None:
        """Build, show and run the Docker-style popup at the cursor (tray thread)."""
        try:
            state = self._state()
        except Exception:
            state = {"running": False}
        running = bool(state.get("running"))

        _init_gdi()
        self._ensure_menu_class()
        px, py = win32api.GetCursorPos()

        # Create hidden first so we can read the popup's per-monitor DPI, then lay out.
        hwnd = win32gui.CreateWindowEx(
            _WS_EX_TOOLWINDOW | _WS_EX_TOPMOST | _WS_EX_LAYERED, _MENU_CLASS, "", _WS_POPUP,
            px, py, 10, 10, self._hwnd, 0, self._hinst, None,
        )
        if not hwnd:
            return
        self._menu_hwnd = hwnd
        try:
            self._dpi = ctypes.windll.user32.GetDpiForWindow(hwnd) or 96
        except Exception:
            self._dpi = 96
        self._ensure_resources()

        rows = self._build_rows(running)
        self._menu_rows, self._menu_w, self._menu_h = self._layout(rows)
        self._menu_hover = -1
        self._menu_result = None
        self._menu_done = False

        x, y = self._place(px, py, self._menu_w, self._menu_h)
        self._apply_frame(hwnd)
        # Show topmost without activating, and never take foreground/capture:
        # that would close the tray overflow flyout and block other tray icons.
        # Dismissal is handled by polling instead (see _poll_dismiss).
        u = ctypes.windll.user32
        u.SetLayeredWindowAttributes(hwnd, 0, 0, _LWA_ALPHA)  # start transparent
        win32gui.SetWindowPos(hwnd, _HWND_TOPMOST, x, y, self._menu_w, self._menu_h,
                              _SWP_NOACTIVATE | _SWP_SHOWWINDOW)
        win32gui.UpdateWindow(hwnd)  # paint into the layered surface before fading
        self._fade_in(hwnd)
        if self._arrow_cursor:
            try:
                win32gui.SetCursor(self._arrow_cursor)
            except Exception:
                pass

        self._pump_menu()

        try:
            win32gui.DestroyWindow(hwnd)
        except Exception:
            pass
        self._menu_hwnd = None
        action = _CMD_TO_ACTION.get(self._menu_result or 0)
        if action:
            self._safe(self._actions.get(action))

    def _fade_in(self, hwnd) -> None:
        """Ramp the layered window's alpha 0 -> 255 (~110ms) for a native fade."""
        u, k = ctypes.windll.user32, ctypes.windll.kernel32
        try:
            for step in range(1, 10):
                u.SetLayeredWindowAttributes(hwnd, 0, (255 * step) // 9, _LWA_ALPHA)
                k.Sleep(12)
        except Exception:
            try:
                u.SetLayeredWindowAttributes(hwnd, 0, 255, _LWA_ALPHA)
            except Exception:
                pass

    def _apply_frame(self, hwnd) -> None:
        """Rounded corners + no system border, so the dark body reads seamless."""
        try:
            dwm = ctypes.windll.dwmapi
            val = ctypes.c_int(_DWMWCP_ROUND)
            dwm.DwmSetWindowAttribute(
                hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE, ctypes.byref(val), ctypes.sizeof(val))
            border = ctypes.c_uint(_DWMWA_COLOR_NONE)
            dwm.DwmSetWindowAttribute(
                hwnd, _DWMWA_BORDER_COLOR, ctypes.byref(border), ctypes.sizeof(border))
        except Exception:
            pass

    def _pump_menu(self) -> None:
        """Modal loop while the popup is up: drain messages, then poll for a
        dismiss on a short sleep (we can't block in GetMessage -- without capture
        the dismiss signal is the global key/button state, not a message)."""
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        msg = wintypes.MSG()
        pmsg = ctypes.byref(msg)
        while not self._menu_done:
            while u.PeekMessageW(pmsg, 0, 0, 0, 1):  # PM_REMOVE
                if msg.message == 0x0012:  # WM_QUIT: re-post for the outer pump.
                    win32gui.PostQuitMessage(0)
                    self._menu_done = True
                    break
                u.TranslateMessage(pmsg)
                u.DispatchMessageW(pmsg)
                if self._menu_done:
                    break
            if self._menu_done:
                break
            self._poll_dismiss()
            k.Sleep(15)

    def _track_leave(self) -> None:
        """Ask for a WM_MOUSELEAVE so hover clears when the cursor exits."""
        try:
            tme = _TRACKMOUSEEVENT(ctypes.sizeof(_TRACKMOUSEEVENT), _TME_LEAVE,
                                   self._menu_hwnd, 0)
            ctypes.windll.user32.TrackMouseEvent(ctypes.byref(tme))
        except Exception:
            pass

    def _poll_dismiss(self) -> None:
        """Dismiss on Esc or a press outside the menu (read from global state)."""
        if win32api.GetAsyncKeyState(_VK_ESCAPE) & 0x8000:
            self._menu_done = True
            return
        if (win32api.GetAsyncKeyState(_VK_LBUTTON) & 0x8000) or \
           (win32api.GetAsyncKeyState(_VK_RBUTTON) & 0x8000):
            try:
                cx, cy = win32api.GetCursorPos()
                l, t, r, b = win32gui.GetWindowRect(self._menu_hwnd)
            except Exception:
                return
            if not (l <= cx < r and t <= cy < b):
                self._menu_done = True  # clicked elsewhere -> close (click passes through)

    def _menu_wndproc(self, hwnd, msg, wparam, lparam):
        if msg == _WM_PAINT:
            try:
                self._paint()
            except Exception:
                pass
            return 0
        if msg == _WM_ERASEBKGND:
            return 1  # painted in WM_PAINT (double-buffered)
        if msg == _WM_MOUSEACTIVATE:
            return _MA_NOACTIVATE  # process the click but never activate (keeps overflow open)
        if msg == _WM_SETCURSOR:
            if self._arrow_cursor:
                win32gui.SetCursor(self._arrow_cursor)
                return 1
        if msg == _WM_MOUSEMOVE:
            if self._arrow_cursor:
                win32gui.SetCursor(self._arrow_cursor)
            x, y = self._xy(lparam)
            self._set_hover(self._hit(x, y))
            self._track_leave()
            return 0
        if msg == _WM_MOUSELEAVE:
            self._set_hover(-1)  # cursor left the menu -> drop the highlight
            return 0
        if msg in (_WM_LBUTTONUP, _WM_RBUTTONUP):
            # Only arrive when the cursor is over us; run the row if it's selectable.
            x, y = self._xy(lparam)
            idx = self._hit(x, y)
            if idx >= 0:
                self._menu_result = self._menu_rows[idx]["cmd"]
                self._menu_done = True
            return 0
        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

    # -- tray message window ---------------------------------------------

    def _wndproc(self, hwnd, msg, wparam, lparam):
        if msg == _WM_TRAY:
            if lparam == win32con.WM_LBUTTONDBLCLK:  # double-click only opens the window
                self._safe(self._on_left)
            elif lparam in (win32con.WM_RBUTTONUP, win32con.WM_CONTEXTMENU):
                try:
                    self._show_menu()
                except Exception:
                    pass
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
