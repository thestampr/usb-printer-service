"""Launch the pywebview-hosted configuration window.

This is a **system-tray app**: a tray icon is shown for the whole app lifetime,
closing the window hides it to the tray (the app keeps running), and it exits only
via the tray menu's Quit. The Flask service runs in-process
(:mod:`ui.web.server_manager`). ``launch_config()`` is the non-blocking entry the
CLI uses — it surfaces an already-running instance or spawns the UI detached so the
terminal isn't held.
"""

from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from ctypes import wintypes
from pathlib import Path

import webview

from config import settings
from ui.theme import NAV_ACTIVE_TEXT, NAV_BG, WINDOW_BG, WINDOW_BORDER
from ui.web import log_bridge, server_manager, startup as app_startup, tray as tray_mod
from ui.web.api import Api
from ui.web.single_instance import ensure_single_instance
from ui.web.tray import Tray

WINDOW_TITLE = "Printer Configuration"

# Taskbar identity. Explorer caches the name/icon per AppID, so bump this string
# if you change _APP_NAME or the icon.
_APP_ID = "TRS.ReceiptPrinterService.1"
_APP_NAME = "Printer Service"

_ROOT = Path(__file__).resolve().parents[2]
_INDEX = os.path.join(os.path.dirname(__file__), "static", "index.html")
_ICON = _ROOT / "assets" / "icon.ico"
_CLI = _ROOT / "printer_cli.py"
_WINDOW_STATE = _ROOT / "config" / "temp.window.json"

# Detached-process creation flags (no console, survives the launching shell).
_DETACHED_PROCESS = 0x00000008
_CREATE_NO_WINDOW = 0x08000000
_CREATE_NEW_PROCESS_GROUP = 0x00000200

# DWM window attributes (Windows 11) used to theme the native title bar.
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_TEXT_COLOR = 36
_DWMWCP_ROUND = 2

_WM_CLOSE = 0x0010


def _colorref(hex_color: str) -> int:
    """#RRGGBB -> Win32 COLORREF (0x00BBGGRR)."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def _find_hwnd(title: str = WINDOW_TITLE, timeout_steps: int = 100) -> int:
    user32 = ctypes.windll.user32
    for _ in range(timeout_steps):
        hwnd = user32.FindWindowW(None, title)
        if hwnd:
            return hwnd
        time.sleep(0.05)
    return 0


def _window_rect(hwnd: int):
    r = wintypes.RECT()
    ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(r))
    return r.left, r.top, r.right - r.left, r.bottom - r.top


def save_geometry(hwnd: int) -> None:
    """Persist the window's position+size so it can be restored next time."""
    try:
        x, y, w, h = _window_rect(hwnd)
        if w < 300 or h < 200:  # minimized / bogus — keep the last good value
            return
        _WINDOW_STATE.parent.mkdir(parents=True, exist_ok=True)
        _WINDOW_STATE.write_text(json.dumps({"x": x, "y": y, "w": w, "h": h}))
    except Exception:
        pass


def _load_geometry():
    try:
        d = json.loads(_WINDOW_STATE.read_text())
        return int(d["x"]), int(d["y"]), int(d["w"]), int(d["h"])
    except Exception:
        return None


def _on_virtual_screen(x: int, y: int, w: int, h: int) -> bool:
    """True if the window's title bar is visibly on some monitor."""
    sm = ctypes.windll.user32.GetSystemMetrics
    vx, vy, vw, vh = sm(76), sm(77), sm(78), sm(79)  # SM_*VIRTUALSCREEN
    cx = x + w // 2
    return vx <= cx <= vx + vw and vy <= y <= vy + vh - 40


def restore_geometry(hwnd: int) -> bool:
    """Apply the saved geometry if present and on-screen. Returns True if applied."""
    g = _load_geometry()
    if not g or not _on_virtual_screen(*g):
        return False
    x, y, w, h = g
    ctypes.windll.user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)  # SWP_NOZORDER
    return True


def force_foreground(hwnd: int) -> None:
    """Restore (if minimized) and reliably bring a window to the front, working
    around Windows' foreground-lock (the caller may not own the foreground)."""
    u = ctypes.windll.user32
    try:
        if u.IsIconic(hwnd):
            u.ShowWindow(hwnd, 9)        # SW_RESTORE
        else:
            u.ShowWindow(hwnd, 5)        # SW_SHOW
        fg = u.GetForegroundWindow()
        cur_t = u.GetWindowThreadProcessId(fg, None)
        my_t = u.GetWindowThreadProcessId(hwnd, None)
        attached = cur_t and my_t and cur_t != my_t
        if attached:
            u.AttachThreadInput(cur_t, my_t, True)
        # Topmost flip nudges it above other windows, then drop back to normal.
        u.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0003)  # HWND_TOPMOST, NOMOVE|NOSIZE
        u.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0003)  # HWND_NOTOPMOST
        u.BringWindowToTop(hwnd)
        u.SetForegroundWindow(hwnd)
        u.SetActiveWindow(hwnd)
        if attached:
            u.AttachThreadInput(cur_t, my_t, False)
    except Exception:
        pass


def place_window(hwnd: int) -> None:
    """Restore the saved geometry, or center on the primary monitor — clamped so a
    window larger than the work area can't land off the top/left."""
    if restore_geometry(hwnd):
        return
    user32 = ctypes.windll.user32
    _, _, w, h = _window_rect(hwnd)
    work = wintypes.RECT()
    user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)  # SPI_GETWORKAREA
    aw, ah = work.right - work.left, work.bottom - work.top
    w, h = min(w, aw - 40), min(h, ah - 40)
    x = work.left + max(0, (aw - w) // 2)
    y = work.top + max(0, (ah - h) // 2)
    user32.SetWindowPos(hwnd, 0, x, y, w, h, 0x0004)  # SWP_NOZORDER (move + size)


def _register_app_id() -> None:
    """Register our AppUserModelID's display name + icon in the registry."""
    try:
        import winreg
        key = winreg.CreateKey(
            winreg.HKEY_CURRENT_USER, r"Software\Classes\AppUserModelId" + "\\" + _APP_ID)
        winreg.SetValueEx(key, "FriendlyName", 0, winreg.REG_SZ, _APP_NAME)
        if _ICON.exists():
            winreg.SetValueEx(key, "IconResource", 0, winreg.REG_SZ, f"{_ICON},0")
        winreg.CloseKey(key)
    except Exception:
        pass


def _ensure_start_menu_shortcut() -> None:
    """Create a Start Menu shortcut carrying our AppID. The Win11 taskbar names
    a window's button from the matching shortcut, else falls back to pythonw.exe."""
    try:
        import pythoncom
        from win32com.shell import shell
        from win32com.propsys import propsys, pscon

        start_dir = os.path.join(
            os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs")
        lnk = os.path.join(start_dir, _APP_NAME + ".lnk")

        try:
            pythoncom.CoInitialize()
        except Exception:
            pass

        def _make_link():
            return pythoncom.CoCreateInstance(
                shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER,
                shell.IID_IShellLink)

        # Skip if a shortcut with the current AppID is already there.
        if os.path.exists(lnk):
            try:
                existing = _make_link()
                existing.QueryInterface(pythoncom.IID_IPersistFile).Load(lnk)
                cur = existing.QueryInterface(propsys.IID_IPropertyStore) \
                    .GetValue(pscon.PKEY_AppUserModel_ID).GetValue()
                if cur == _APP_ID:
                    return
            except Exception:
                pass

        if getattr(sys, "frozen", False):
            target, args = sys.executable, "--config"
        else:
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            target = pyw if os.path.exists(pyw) else sys.executable
            args = '"%s" --config' % _CLI

        link = _make_link()
        link.SetPath(target)
        link.SetArguments(args)
        if _ICON.exists():
            link.SetIconLocation(str(_ICON), 0)
        link.SetWorkingDirectory(str(_ROOT))
        link.SetDescription(_APP_NAME)
        store = link.QueryInterface(propsys.IID_IPropertyStore)
        store.SetValue(pscon.PKEY_AppUserModel_ID, propsys.PROPVARIANTType(_APP_ID))
        store.Commit()
        link.QueryInterface(pythoncom.IID_IPersistFile).Save(lnk, True)
    except Exception:
        pass


def _set_window_appid(hwnd: int) -> None:
    """Set the window's AppID property (the process-wide AppID doesn't stick to
    pywebview's window). Done before the window is shown."""
    try:
        c = ctypes

        class GUID(c.Structure):
            _fields_ = [("d1", c.c_uint32), ("d2", c.c_uint16),
                        ("d3", c.c_uint16), ("d4", c.c_ubyte * 8)]

        class PROPERTYKEY(c.Structure):
            _fields_ = [("fmtid", GUID), ("pid", c.c_uint32)]

        class PROPVARIANT(c.Structure):
            _fields_ = [("vt", c.c_ushort), ("r1", c.c_ushort), ("r2", c.c_ushort),
                        ("r3", c.c_ushort), ("p1", c.c_void_p), ("p2", c.c_void_p)]

        def _guid(d1, d2, d3, rest):
            return GUID(d1, d2, d3, (c.c_ubyte * 8)(*rest))

        # IID_IPropertyStore and PKEY_AppUserModel_ID.
        iid_store = _guid(0x886D8EEB, 0x8CF2, 0x4446,
                          (0x8D, 0x02, 0xCD, 0xBA, 0x1D, 0xBD, 0xCF, 0x99))
        pkey = PROPERTYKEY(_guid(0x9F4C2855, 0x9F79, 0x4B39,
                                 (0xA8, 0xD0, 0xE1, 0xD4, 0x2D, 0xE1, 0xD5, 0xF3)), 5)

        try:
            c.windll.ole32.CoInitialize(None)
        except Exception:
            pass
        sh = c.windll.shell32
        sh.SHGetPropertyStoreForWindow.argtypes = [
            c.c_void_p, c.POINTER(GUID), c.POINTER(c.c_void_p)]
        store = c.c_void_p()
        if sh.SHGetPropertyStoreForWindow(hwnd, c.byref(iid_store), c.byref(store)) != 0 or not store:
            return
        ole32 = c.windll.ole32
        ole32.CoTaskMemAlloc.restype = c.c_void_p
        ole32.CoTaskMemAlloc.argtypes = [c.c_size_t]
        nbytes = (len(_APP_ID) + 1) * 2
        mem = ole32.CoTaskMemAlloc(nbytes)
        c.memmove(mem, c.create_unicode_buffer(_APP_ID), nbytes)
        pv = PROPVARIANT()
        pv.vt = 31  # VT_LPWSTR
        pv.p1 = mem
        vtbl = c.cast(store, c.POINTER(c.c_void_p))[0]
        slots = c.cast(vtbl, c.POINTER(c.c_void_p))
        p_setvalue = c.WINFUNCTYPE(
            c.c_long, c.c_void_p, c.POINTER(PROPERTYKEY), c.POINTER(PROPVARIANT))
        p_void = c.WINFUNCTYPE(c.c_long, c.c_void_p)
        p_setvalue(slots[6])(store, c.byref(pkey), c.byref(pv))  # IPropertyStore::SetValue
        p_void(slots[7])(store)                                  # ::Commit
        ole32.PropVariantClear(c.byref(pv))
        p_void(slots[2])(store)                                  # ::Release
    except Exception:
        pass


def _set_window_icon(hwnd: int) -> None:
    """Set the title-bar + taskbar icon from assets/icon.ico."""
    if not _ICON.exists():
        return
    user32 = ctypes.windll.user32
    user32.LoadImageW.restype = ctypes.c_void_p
    user32.SendMessageW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p]
    image_icon, lr_loadfromfile, lr_defaultsize = 1, 0x0010, 0x0040
    wm_seticon, icon_small, icon_big = 0x0080, 0, 1
    set_class = getattr(user32, "SetClassLongPtrW", user32.SetClassLongW)
    set_class.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    big = user32.LoadImageW(None, str(_ICON), image_icon, 0, 0, lr_loadfromfile | lr_defaultsize)
    small = user32.LoadImageW(None, str(_ICON), image_icon, 16, 16, lr_loadfromfile)
    if big:
        user32.SendMessageW(hwnd, wm_seticon, icon_big, big)
        set_class(hwnd, -14, big)
    if small:
        user32.SendMessageW(hwnd, wm_seticon, icon_small, small)
        set_class(hwnd, -34, small)


def _apply_titlebar_theme(window=None) -> None:
    """Theme the native title bar (DWM) and set the window icon."""
    try:
        hwnd = _find_hwnd()
        if not hwnd:
            return
        place_window(hwnd)
        dwm = ctypes.windll.dwmapi

        def set_attr(attr: int, value: int) -> None:
            dwm.DwmSetWindowAttribute(hwnd, attr, ctypes.byref(ctypes.c_int(value)), 4)

        set_attr(_DWMWA_CAPTION_COLOR, _colorref(NAV_BG))
        set_attr(_DWMWA_TEXT_COLOR, _colorref(NAV_ACTIVE_TEXT))
        set_attr(_DWMWA_BORDER_COLOR, _colorref(WINDOW_BORDER))
        set_attr(_DWMWA_WINDOW_CORNER_PREFERENCE, _DWMWCP_ROUND)
        _set_window_icon(hwnd)
        _set_window_appid(hwnd)
    except Exception:
        pass


def _spawn_detached_ui(minimized: bool) -> None:
    """Start the UI in a detached process so the launching shell isn't blocked."""
    if getattr(sys, "frozen", False):
        cmd = [sys.executable, "--config"]
    else:
        pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        runner = pyw if os.path.exists(pyw) else sys.executable
        cmd = [runner, str(_CLI), "--config"]
    if minimized:
        cmd.append("--minimized")
    env = dict(os.environ, PRINTER_UI_CHILD="1")
    subprocess.Popen(
        cmd, cwd=str(_ROOT), env=env, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True,
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
    )


def launch_config(minimized: bool = False) -> None:
    """Non-blocking CLI entry for ``printer --config``.

    If we're the detached child, run the UI. Otherwise: surface an already-running
    instance, or spawn the UI detached and return immediately (terminal freed).
    """
    if os.environ.get("PRINTER_UI_CHILD") == "1":
        launch(minimized=minimized)
        return
    if tray_mod.signal_show():
        return
    _spawn_detached_ui(minimized)


def launch(minimized: bool = False) -> None:
    """Open the config UI (single-instance) with in-process service + tray."""
    if not ensure_single_instance(WINDOW_TITLE):
        return

    # Claim our taskbar identity (name + icon) before the window is created.
    _register_app_id()
    _ensure_start_menu_shortcut()
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(_APP_ID)
    except Exception:
        pass

    # Run-at-startup is on by default (opt-out); apply once per machine.
    try:
        app_startup.apply_default()
    except Exception:
        pass

    svc = settings.get_all().get("SERVICE", {})
    log_bridge.install(debug=bool(svc.get("debug", False)))

    api = Api()

    window = webview.create_window(
        WINDOW_TITLE, url=_INDEX, js_api=api,
        width=1300, height=820, min_size=(940, 620),
        hidden=True, background_color=WINDOW_BG,  # revealed only after the page paints
    )
    api.bind_window(window)

    state = {"force_quit": False, "revealed": False}

    def _reveal():
        # Theme + position the (still-hidden) window, then show it — so the user
        # never sees WebView2's white initialization flash; by now the splash is painted.
        if state["revealed"]:
            return
        state["revealed"] = True
        _apply_titlebar_theme()
        if not minimized:
            try:
                window.show()
            except Exception:
                pass

    window.events.loaded += lambda: threading.Thread(target=_reveal, daemon=True).start()
    # Fallback so the window can never stay invisible if 'loaded' doesn't fire.
    threading.Timer(3.0, lambda: threading.Thread(target=_reveal, daemon=True).start()).start()

    # Live log lines -> in-app console (history is also kept in log_bridge.RING).
    def _sink(lines):
        try:
            window.evaluate_js(
                "window.App && App.service && App.service._push(%s)" % json.dumps(lines)
            )
        except Exception:
            pass

    log_bridge.set_sink(_sink)

    def _show_main():
        try:
            window.show()
        except Exception:
            pass
        hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            # Re-apply the saved geometry so it returns exactly where it was,
            # then restore (if minimized) and pull it to the foreground.
            restore_geometry(hwnd)
            force_foreground(hwnd)

    def real_quit(force: bool = False) -> None:
        # Explicit quit still protects unsaved settings (unlike Spotify).
        if api.dirty and not force:
            _show_main()
            try:
                window.evaluate_js("window.App && App.confirmQuit && App.confirmQuit()")
            except Exception:
                pass
            return
        state["force_quit"] = True
        hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            ctypes.windll.user32.PostMessageW(hwnd, _WM_CLOSE, 0, 0)
        else:  # no main window found; tear down directly
            _finalize()
            try:
                window.destroy()
            except Exception:
                pass

    api.bind_quit(real_quit)

    def _check_update_from_tray():
        # Run the existing in-UI update flow (check -> confirm -> update).
        _show_main()
        try:
            window.evaluate_js(
                "var b=document.getElementById('update-btn'); b && b.click()"
            )
        except Exception:
            pass

    def _restart_app():
        # Spawn a detached helper that waits for this process to exit, then relaunches
        # the UI; then quit. (A clean restart of the whole app.)
        if getattr(sys, "frozen", False):
            relaunch = [sys.executable, "--config"]
        else:
            pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            runner = pyw if os.path.exists(pyw) else sys.executable
            relaunch = [runner, str(_CLI), "--config"]
        # Preserve visibility: if we're sleeping in the tray (window hidden), come
        # back silently into the tray instead of popping the window open.
        user32 = ctypes.windll.user32
        user32.FindWindowW.restype = ctypes.c_void_p
        user32.IsWindowVisible.argtypes = [ctypes.c_void_p]
        _hwnd = user32.FindWindowW(None, WINDOW_TITLE)
        if not (_hwnd and user32.IsWindowVisible(_hwnd)):
            relaunch.append("--minimized")
        waiter = (
            "import ctypes,subprocess\n"
            "k=ctypes.windll.kernel32\n"
            "h=k.OpenProcess(0x00100000,False,%d)\n" % os.getpid()
            + "if h: k.WaitForSingleObject(h,15000); k.CloseHandle(h)\n"
            "subprocess.Popen(%r)\n" % (relaunch,)
        )
        try:
            subprocess.Popen(
                [relaunch[0], "-c", waiter], cwd=str(_ROOT), close_fds=True,
                creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
            )
        except Exception:
            return
        real_quit(force=True)

    # The tray icon owns the native right-click menu; its actions run here.
    tray = Tray(
        str(_ICON), "Printer Service",
        on_left_click=_show_main,
        actions={
            "open": _show_main,
            "start": server_manager.manager.start,
            "stop": server_manager.manager.stop,
            "restart": lambda: (server_manager.manager.stop(), server_manager.manager.start()),
            "check_update": _check_update_from_tray,
            "restart_app": _restart_app,
            "quit": real_quit,
        },
        state_provider=server_manager.manager.status,
    )
    tray.start()
    # Tray-app model: the icon is present for the whole app lifetime.
    tray.show_icon()

    # Tooltip + Service-page button reflect the server state (icon stays put).
    def _on_server_change(running: bool) -> None:
        tray.set_tooltip("Printer Service · Running" if running else "Printer Service")
        try:
            window.evaluate_js(
                "window.App && App.service && App.service.refresh && App.service.refresh()"
            )
        except Exception:
            pass

    server_manager.manager.on_change = _on_server_change

    def _finalize() -> bool:
        """Tear down service + tray so the GUI loop can end. GUI thread."""
        state["force_quit"] = True
        # Detach the webview sinks first: stopping the service calls evaluate_js
        # (log sink + on_change), which deadlocks the close if run while the
        # window is tearing down (hangs Quit/Restart with the service running).
        log_bridge.set_sink(None)
        server_manager.manager.on_change = None
        _hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
        if _hwnd:
            save_geometry(_hwnd)
        try:
            server_manager.manager.stop()
        except Exception:
            pass
        try:
            tray.stop()
        except Exception:
            pass
        return True

    def _on_closing(*_args):
        # System-tray app: closing always hides to the tray (state preserved);
        # the app exits only via the tray menu's Quit (-> real_quit -> force_quit).
        if state["force_quit"] or api.allow_close:
            return _finalize()
        _hwnd = ctypes.windll.user32.FindWindowW(None, WINDOW_TITLE)
        if _hwnd:
            save_geometry(_hwnd)  # remember where it was so awake/restart restores it
        threading.Thread(target=window.hide, daemon=True).start()
        return False

    window.events.closing += _on_closing
    webview.start(gui="edgechromium")


if __name__ == "__main__":
    launch()
