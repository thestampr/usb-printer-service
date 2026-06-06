"""Receipt printer driver targeting ESC/POS USB thermal printers."""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Optional

from config.settings import PRINTER
from printer.utils import get_real_path

try:
    from PIL import Image
except ImportError:
    Image = ImageDraw = None

try:
    escpos_printer = importlib.import_module("escpos.printer")
except ModuleNotFoundError:
    escpos_printer = None
try:
    win32print = importlib.import_module("win32print")
    WIN32PRINT_AVAILABLE = True
except ModuleNotFoundError:
    win32print = None
    WIN32PRINT_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


def list_printers() -> list[dict[str, str]]:
    """Return installed Windows printers as ``{"name", "port"}`` dicts.

    Empty list when win32print is unavailable (non-Windows or missing pywin32).
    """
    if not WIN32PRINT_AVAILABLE:
        return []

    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    printers: list[dict[str, str]] = []
    try:
        for info in win32print.EnumPrinters(flags, None, 2):
            name = (info.get("pPrinterName") or "").strip()
            if not name:
                continue
            printers.append({"name": name, "port": (info.get("pPortName") or "").strip()})
    except Exception as exc:  # pragma: no cover - platform specific
        LOGGER.warning("Failed to enumerate printers: %s", exc)
    return printers


def get_printer_port(name: str) -> Optional[str]:
    """Return the port a Windows printer queue is bound to, or None."""
    if not WIN32PRINT_AVAILABLE or not name:
        return None
    try:
        handle = win32print.OpenPrinter(name)
    except Exception:
        return None
    try:
        info = win32print.GetPrinter(handle, 2)
        port = info.get("pPortName")
        return port.strip() if port else None
    except Exception:
        return None
    finally:
        win32print.ClosePrinter(handle)


def test_connection(name: str, port: str = "") -> tuple[bool, str]:
    """Non-destructively verify a printer queue is reachable.

    Opens the Windows print queue by name (no document is started, so nothing
    is printed) and confirms the prerequisites for the Win32Raw driver path.
    Returns ``(ok, message)``.
    """
    if escpos_printer is None:
        return False, "python-escpos is not installed; cannot print."
    if not WIN32PRINT_AVAILABLE:
        return False, "pywin32 (win32print) is not installed."

    name = (name or "").strip()
    if not name:
        return False, "Printer name is required."

    try:
        handle = win32print.OpenPrinter(name)
    except Exception as exc:
        return False, f"Could not open printer '{name}': {exc}"
    try:
        info = win32print.GetPrinter(handle, 2)
    except Exception as exc:
        return False, f"Could not query printer '{name}': {exc}"
    finally:
        win32print.ClosePrinter(handle)

    actual_port = (info.get("pPortName") or "").strip()
    port = (port or "").strip()
    if port and actual_port and port.lower() != actual_port.lower():
        return True, f"Reachable, but it is on port '{actual_port}', not '{port}'."
    return True, f"'{name}' is reachable on port '{actual_port or port or 'unknown'}'."


class ReceiptPrinter:
    """Simple wrapper around python-escpos to output UTF-8 Thai receipts."""

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or PRINTER
        self.device = None
        self.pixel_width = self.config.get("pixel_width", 384)

    def connect(self):
        """Connect to the configured printer using Win32Raw or fallback."""
        
        if self.device is not None:
            return self.device
        if escpos_printer is None:
            raise RuntimeError("python-escpos is not installed; cannot send data to printer")
        if not WIN32PRINT_AVAILABLE:
            raise RuntimeError(
                "Win32Raw printing requires the 'pywin32' package (win32print); "
                "install it via 'pip install pywin32' and restart the service."
            )

        usb_name = self.config.get("usb_name") or "XP-58"
        usb_port = self.config.get("usb_port") or "USB001"
        try:
            # Win32Raw talks directly to a Windows printer queue by name/port.
            self.device = escpos_printer.Win32Raw(usb_name, port=usb_port)
        except Exception as exc:  # pragma: no cover - hardware specific
            LOGGER.error("Unable to connect to printer %s (%s): %s", usb_name, usb_port, exc)
            raise RuntimeError("Failed to connect to USB receipt printer") from exc

        return self.device

    def print_image(self, path: str | Path | "Image.Image", scale: int = 100) -> None:
        if not path:
            return

        device = self.connect()
        # Label for error logs, valid for both branches below (a bare image_path
        # would be unbound here when a PIL image is passed -> UnboundLocalError).
        source = "receipt image"

        if isinstance(path, Image.Image):
            pil_image = path
            LOGGER.debug("Printing PIL Image object (scale=%s%%)", scale)
        else:
            image_path = get_real_path(path)
            source = str(image_path)
            if not image_path.exists():
                LOGGER.warning("Header image %s not found; skipping", path)
                return
            LOGGER.debug("Printing image %s (scale=%s%%)", image_path, scale)

            if Image is None:
                try:
                    device.image(str(image_path))
                except Exception as exc:
                    LOGGER.error("Failed to print image %s: %s", image_path, exc)
                    raise RuntimeError("Failed to print header image") from exc
                return

            try:
                pil_image = Image.open(image_path)
            except Exception as exc:
                LOGGER.error("Failed to open image %s: %s", image_path, exc)
                raise RuntimeError("Failed to open image for printing") from exc

        processed = self._prepare_bitmap(pil_image, scale)

        try:
            device.image(processed, impl="bitImageColumn")
        except Exception as exc:
            LOGGER.error("Failed to print processed image %s: %s", source, exc)
            raise RuntimeError("Failed to print receipt image") from exc

    def cut(self) -> None:
        device = self.connect()
        try:
            device.cut()
        except AttributeError:
            LOGGER.debug("Printer does not support cut operation; sending form feed")
            device.control("LF")

    def kick_drawer(self, pin: int = 2) -> None:
        """Kick the cash drawer."""
        device = self.connect()
        try:
            device.cashdraw(pin)
        except AttributeError:
            LOGGER.debug("Using raw ESC/POS command for drawer kick")
            if pin == 2:
                device.text("\x1b\x70\x00\x19\xfa")
            elif pin == 5:
                device.text("\x1b\x70\x01\x19\xfa")
            else:
                raise ValueError("Invalid pin for cash drawer kick; must be 2 or 5")

    def feed(self, lines: int = 1) -> None:
        """Advance paper by the requested number of lines."""
        if lines <= 0:
            return
        device = self.connect()
        try:
            device.text("\n" * int(lines))
        except Exception as exc:
            LOGGER.error("Failed to feed printer %s lines: %s", lines, exc)
            raise RuntimeError("Failed to feed paper") from exc

    def disconnect(self) -> None:
        if not self.device:
            return
        close_fn = getattr(self.device, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:
                LOGGER.debug("Failed to close printer device", exc_info=True)
        self.device = None

    def _prepare_bitmap(self, image: "Image.Image", scale: int = 100):
        if image.mode != "L":
            image = image.convert("L")

        if image.width == 0 or image.height == 0:
            raise RuntimeError("Image has invalid dimensions")

        # Determine target width based on percentage of paper width (pixel_width)
        # scale=100 means use full paper width
        target_width = int(self.pixel_width * (scale / 100.0))
        target_width = max(1, target_width)

        # Calculate ratio to resize image to strictly fit/match target_width
        # We usually want to maintain aspect ratio
        scale_ratio = target_width / float(image.width)
        
        # Note: If scale=100 and image is larger than pixel_width, this downscales it (good).
        # If image is smaller, this upscales it (pixelated, but fits request "Fit to Width").
        # If user wants native size, they'd have to calculate %? 
        # But generally for receipts, fitting/centering is desired behavior.
        
        new_width = max(1, int(image.width * scale_ratio))
        new_height = max(1, int(image.height * scale_ratio))
        
        # Only resize if necessary (optimization, though float comparison might be fuzzy)
        if new_width != image.width or new_height != image.height:
            image = image.resize((new_width, new_height), Image.LANCZOS)

        image = image.convert("1")

        # Center on canvas if smaller than pixel_width (it shouldn't be larger as we scaled to pixel_width max)
        if image.width < self.pixel_width:
            canvas = Image.new("1", (self.pixel_width, image.height), 1)
            x_offset = max(0, (self.pixel_width - image.width) // 2)
            canvas.paste(image, (x_offset, 0))
            image = canvas

        return image


__all__ = ["ReceiptPrinter", "list_printers", "get_printer_port", "test_connection"]
