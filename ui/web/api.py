"""The ``js_api`` bridge exposed to the web UI.

Every public method on :class:`Api` is callable from JavaScript as
``window.pywebview.api.<name>(...)``; pywebview marshals arguments and return
values as JSON. The bridge is a thin wrapper over the already-decoupled backend
(``config``, ``printer``, ``common``); no business logic lives here.

Failure convention: action methods return ``{"ok": False, "error": "<msg>"}``;
simple getters return their data directly.
"""

from __future__ import annotations

import base64
import threading
from io import BytesIO
from typing import Any, Callable, Optional

import webview

from common import updater
from common.interface import PayloadInfo
from config import dummy, settings
from l10n import LocaleEN, LocaleTH
from printer import driver
from printer.driver import ReceiptPrinter
from printer.renderer import generate_receipt_image
from printer.template import validate_payload
from ui.actions import (
    open_docs as _open_docs,
    open_driver_downloads_page as _open_drivers,
    open_github_repo as _open_github,
)
from ui.layout import FILE_PICKER_FIELDS
from ui.web import log_bridge, server_manager, startup as app_startup
from ui.web.preview_effect import apply_paper_effect


def _locale_for(code: Optional[str]):
    return LocaleTH() if code == "th" else LocaleEN()


class Api:
    """Bridge object passed to ``webview.create_window(js_api=...)``."""

    def __init__(self) -> None:
        self._window: Optional["webview.Window"] = None
        self.dirty = False
        self.allow_close = False
        self._quit_cb: Optional[Callable[[bool], None]] = None

    def bind_window(self, window: "webview.Window") -> None:
        """Attach the created window so native dialogs can be opened."""
        self._window = window

    def bind_quit(self, quit_cb: Callable[[bool], None]) -> None:
        """Wire the app-level quit/teardown routine (set by ui.web.app)."""
        self._quit_cb = quit_cb

    def set_dirty(self, dirty: bool) -> None:
        """JS reports the unsaved-changes state so the close handler can prompt."""
        self.dirty = bool(dirty)

    def request_close(self) -> None:
        """JS confirmed closing with unsaved changes -> full teardown + exit."""
        if self._quit_cb:
            self._quit_cb(True)
        else:  # fallback if quit isn't wired (shouldn't happen)
            self.allow_close = True
            if self._window:
                try:
                    self._window.destroy()
                except Exception:
                    pass

    def request_quit(self) -> None:
        """JS confirmed Quit from the unsaved-changes modal -> teardown + exit."""
        if self._quit_cb:
            self._quit_cb(True)

    # -- Config (config/settings.py) -------------------------------------

    def get_config(self) -> dict[str, Any]:
        return settings.get_all()

    def get_config_defaults(self) -> dict[str, Any]:
        return settings.get_defaults()

    def save_config(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            paper_width = (data.get("PRINTER") or {}).get("paper_width")
            if paper_width:
                settings.apply_paper_width(data, paper_width)
            settings.save_all(data)
            return {"ok": True}
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": str(exc)}

    # -- Dummy payload (config/dummy.py) ---------------------------------

    def get_dummy(self) -> dict[str, Any]:
        return dummy.load()

    def get_dummy_defaults(self) -> dict[str, Any]:
        return dummy.get_defaults()

    def save_dummy(self, data: dict[str, Any]) -> dict[str, Any]:
        try:
            dummy.save(data)
            return {"ok": True}
        except Exception as exc:  # pragma: no cover - defensive
            return {"ok": False, "error": str(exc)}

    # -- Live preview (renders to PNG, never to the printer) --------------

    def render_preview(
        self, layout: dict[str, Any], payload: dict[str, Any], locale: str = "en"
    ) -> dict[str, Any]:
        try:
            validated = validate_payload(payload)
        except ValueError as exc:
            # Soft-fail: caller keeps the last good PNG.
            return {"ok": False, "error": str(exc)}
        try:
            info = PayloadInfo.from_dict(validated)
            img = generate_receipt_image(layout, info, locale=_locale_for(locale))
            framed = apply_paper_effect(img)
            buf = BytesIO()
            # compress_level=1 ~halves encode time vs the default; the larger
            # bytes are cheap to ship over the in-process bridge.
            framed.save(buf, format="PNG", compress_level=1)
            b64 = base64.b64encode(buf.getvalue()).decode("ascii")
            return {
                "ok": True,
                "png": f"data:image/png;base64,{b64}",
                "width": framed.width,
                "height": framed.height,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # -- Printer picker (printer/driver.py) ------------------------------

    def list_printers(self) -> list[dict[str, str]]:
        return driver.list_printers()

    def get_printer_port(self, name: str) -> str:
        return driver.get_printer_port(name) or ""

    def test_connection(self, name: str, port: str = "") -> dict[str, Any]:
        ok, message = driver.test_connection(name, port)
        return {"ok": ok, "message": message}

    # -- Test print (the ONE method that drives the physical printer) -----

    def test_print(
        self,
        config: Optional[dict] = None,
        payload: Optional[dict] = None,
        locale: str = "en",
    ) -> dict[str, Any]:
        """Print a test receipt (WYSIWYG with the preview). Explicit button only.

        Uses the live (possibly unsaved) config and payload when provided so it
        matches what the preview shows; falls back to saved settings/dummy.
        """
        try:
            cfg = config or settings.get_all()
            printer_cfg = cfg.get("PRINTER", {})
            layout_cfg = cfg.get("LAYOUT", {})
            data = validate_payload(payload if payload is not None else dummy.load())
            info = PayloadInfo.from_dict(data)
            img = generate_receipt_image(layout_cfg, info, locale=_locale_for(locale))
            printer = ReceiptPrinter(printer_cfg)
            try:
                printer.print_image(img)
                printer.cut()
            finally:
                printer.disconnect()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # -- Image thumbnail (resolves relative paths / base64 to a data URL) -

    def image_thumb(self, path: str, size: int = 200) -> str:
        """Return a small PNG data URL for an image path or base64/data-URI.

        Resolves relative paths the same way the renderer does so the editor
        thumbnail shows the real image. Empty string when it can't be loaded.
        """
        path = (path or "").strip()
        if not path:
            return ""
        try:
            from PIL import Image

            from printer.utils import get_real_path

            if path.startswith("data:"):
                _, _, b64 = path.partition(",")
                src = BytesIO(base64.b64decode(b64))
                img = Image.open(src)
            else:
                img = Image.open(get_real_path(path))
            img = img.convert("RGBA")
            img.thumbnail((int(size), int(size)))
            buf = BytesIO()
            img.save(buf, format="PNG")
            return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        except Exception:
            return ""

    # -- Native file dialog ----------------------------------------------

    def pick_file(self, field: str) -> str:
        """Open a native file picker for a ``"SECTION|key"`` file field."""
        if self._window is None:
            return ""
        section, _, key = field.partition("|")
        meta = FILE_PICKER_FIELDS.get((section, key))
        file_types: tuple[str, ...] = ()
        if meta:
            file_types = tuple(
                _to_webview_filetype(ft) for ft in meta.get("filetypes", [])
            )
        try:
            result = self._window.create_file_dialog(
                webview.OPEN_DIALOG, file_types=file_types
            )
        except Exception:
            return ""
        if result:
            return result[0]
        return ""

    # -- Version / update (common/updater.py) ----------------------------

    def get_version_info(self) -> dict[str, Any]:
        try:
            return {
                "current": updater.get_current_version(),
                "is_dev": updater.is_dev_checkout(),
            }
        except Exception as exc:
            return {"current": "", "is_dev": False, "error": str(exc)}

    def check_update(self) -> dict[str, Any]:
        try:
            return updater.check_for_update()
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    def run_update(self) -> dict[str, Any]:
        try:
            updater.launch_updater("none")
            # The updater waits for this process to exit before replacing files,
            # but closing the window only hides to the tray — so force a full quit.
            # Brief delay lets the JS response/toast render first.
            if self._quit_cb:
                t = threading.Timer(0.6, lambda: self._quit_cb(True))
                t.daemon = True
                t.start()
            return {"ok": True}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # -- Service control (in-process Flask server; see server_manager) ----

    def service_status(self) -> dict[str, Any]:
        return server_manager.manager.status()

    def start_service(self) -> dict[str, Any]:
        return server_manager.manager.start()

    def stop_service(self) -> dict[str, Any]:
        return server_manager.manager.stop()

    def attach_console(self) -> dict[str, Any]:
        """Return the buffered log history to seed the in-app console."""
        return {"ok": True, "lines": log_bridge.history()}

    # -- App settings (Settings page) ------------------------------------

    def get_app_settings(self) -> dict[str, Any]:
        return {"run_at_startup": app_startup.is_enabled()}

    def set_run_at_startup(self, enabled: bool) -> dict[str, Any]:
        try:
            if enabled:
                app_startup.enable()
            else:
                app_startup.disable()
            return {"ok": True, "run_at_startup": app_startup.is_enabled()}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    # -- External links (open in the system default app) ------------------

    def open_drivers(self) -> None:
        _open_drivers()

    def open_docs(self) -> None:
        _open_docs()

    def open_github(self) -> None:
        _open_github()


def _to_webview_filetype(ft: Any) -> str:
    """Convert a Tk ``(label, "*.a *.b")`` filetype to pywebview ``"label (*.a;*.b)"``."""
    label, pattern = ft[0], ft[1]
    exts = ";".join(str(pattern).split())
    return f"{label} ({exts})"
