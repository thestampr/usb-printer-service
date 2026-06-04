"""Side-effecting helpers shared by the CLI and the web UI.

Test printing and opening external pages, with no GUI-toolkit dependency.
Relocated out of the legacy Tkinter ``ui/main.py`` during the web-UI migration.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from common.interface import PayloadInfo
from config import dummy, settings
from l10n import LocaleEN, LocaleTH
from printer.driver import ReceiptPrinter
from printer.renderer import generate_receipt_image

if TYPE_CHECKING:
    from config.settings import Config
    from l10n.abc import Locale

_REPO_ROOT = Path(__file__).resolve().parents[1]


def print_preview(config: "Optional[Config]" = None, locale: "Optional[Locale]" = None) -> None:
    """Print the saved dummy payload as a test receipt using ``config``."""
    current_config = config or settings.get_all()
    printer_cfg = current_config.get("PRINTER", {})
    layout_cfg = current_config.get("LAYOUT", {})

    info = PayloadInfo.from_dict(dummy.load())
    if locale is None:
        rc = layout_cfg.get("receipt_locale", "en")
        locale = LocaleTH() if rc == "th" else LocaleEN()

    img = generate_receipt_image(layout_cfg, info, locale=locale)

    printer = ReceiptPrinter(printer_cfg)
    try:
        printer.print_image(img)
        printer.cut()
    except Exception as e:
        raise Exception(f"Print Error: {e}")
    finally:
        printer.disconnect()


def open_url(url: str) -> None:
    """Open a URL in the default browser."""
    if sys.platform == "win32":
        os.startfile(url)  # noqa: S606 - trusted URL in the default browser
    else:
        import webbrowser

        webbrowser.open(url)


def open_driver_downloads_page() -> None:
    """Open the bundled printer-driver page, or the vendor page as a fallback."""
    drivers_html = _REPO_ROOT / "assets" / "printer_drivers.html"
    if drivers_html.exists():
        if sys.platform == "win32":
            os.startfile(str(drivers_html))  # noqa: S606
        else:
            import webbrowser

            webbrowser.open(drivers_html.as_uri())
    else:
        open_url("https://www.xprinter.co.th/en/pages/45381-Download%20Driver")


def open_github_repo() -> None:
    """Open the project's GitHub repository."""
    open_url("https://github.com/thestampr/usb-printer-service")


def open_docs() -> None:
    """Open the bundled developer documentation, if present."""
    docs_html = _REPO_ROOT / "assets" / "docs.html"
    if not docs_html.exists():
        return
    if sys.platform == "win32":
        os.startfile(str(docs_html))  # noqa: S606
    else:
        import webbrowser

        webbrowser.open(docs_html.as_uri())
