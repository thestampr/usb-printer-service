"""Receipt printer driver targeting ESC/POS USB thermal printers."""
from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Optional, Tuple

from config.settings import LAYOUT, PRINTER
from printer.utils import (
    ALIGN_CENTER_TOKEN,
    ALIGN_LEFT_TOKEN,
    ALIGN_RIGHT_TOKEN,
    SMALL_TEXT_TOKEN,
    get_real_path
)

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:  # pragma: no cover
    Image = ImageDraw = ImageFont = None

try:  # pragma: no cover - resolved only when optional dependency installed
    escpos_printer = importlib.import_module("escpos.printer")
except ModuleNotFoundError:  # pragma: no cover - library might not be installed locally
    escpos_printer = None
try:  # pragma: no cover - optional win32 dependency
    importlib.import_module("win32print")
    WIN32PRINT_AVAILABLE = True
except ModuleNotFoundError:  # pragma: no cover - warn later during connect
    WIN32PRINT_AVAILABLE = False

LOGGER = logging.getLogger(__name__)


class ReceiptPrinter:
    """Simple wrapper around python-escpos to output UTF-8 Thai receipts."""

    def __init__(self, config: Optional[dict] = None) -> None:
        self.config = config or PRINTER
        self.device = None
        self.encoding = self.config.get("encoding", "utf-8")
        self.pixel_width = self.config.get("pixel_width", 384)
        self.font = LAYOUT.get("font_family", "Sarabun-SemiBold")
        self.font_path = get_real_path(LAYOUT.get("font_path", "assets/fonts/Sarabun/Sarabun-SemiBold.ttf"))
        self.font_size = LAYOUT.get("font_size", 24)
        self.font_size_small = LAYOUT.get("font_size_small", max(12, self.font_size - 6))
        self.line_spacing = LAYOUT.get("line_spacing", 6)
        self._font_cache = {}

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
            LOGGER.exception("Unable to connect to printer %s (%s)", usb_name, usb_port)
            raise RuntimeError("Failed to connect to USB receipt printer") from exc

        return self.device

    def print_text(self, text: str) -> None:
        """Render text using Sarabun font and send as bitmap image."""
        if not text:
            return
        if Image is None or ImageDraw is None or ImageFont is None:
            raise RuntimeError("Pillow is not installed; cannot render Thai text as image")
        if not self.font_path.exists():
            raise RuntimeError(f"Font file not found: {self.font_path}")

        LOGGER.debug("Printing text block (%d chars)", len(text))

        lines_meta = self._prepare_lines(text)
        total_height = sum(meta[3] for meta in lines_meta)
        if total_height <= 0:
            total_height = self.font_size + self.line_spacing

        # Create white canvas for black text
        image = Image.new("1", (self.pixel_width, total_height), 1)
        draw = ImageDraw.Draw(image)

        y_offset = 0
        for content, alignment, font, line_height in lines_meta:
            if not content:
                y_offset += line_height
                continue

            bbox = draw.textbbox((0, 0), content, font=font)
            line_width = (bbox[2] - bbox[0]) if bbox else 0
            if alignment == "center":
                x_offset = max(0, (self.pixel_width - line_width) // 2)
            elif alignment == "right":
                x_offset = max(0, self.pixel_width - line_width)
            else:
                x_offset = 0

            draw.text((x_offset, y_offset), content, font=font, fill=0)
            y_offset += line_height

        # Crop excess white space at bottom
        bbox = image.getbbox()
        if bbox:
            image = image.crop((0, 0, self.pixel_width, bbox[3] + self.line_spacing))

        device = self.connect()
        try:
            device.image(image, impl="bitImageColumn")
        except Exception as exc:
            LOGGER.exception("Failed to print rendered text image")
            raise RuntimeError("Failed to print text as image") from exc

    def _prepare_lines(self, text: str):
        lines_meta = []
        for raw_line in text.splitlines():
            content, alignment, font_size = self._extract_line_style(raw_line)
            font = self._get_font(font_size)
            line_height = font_size + self.line_spacing
            lines_meta.append((content, alignment, font, line_height))
        return lines_meta

    def _extract_line_style(self, line: str) -> Tuple[str, str, int]:
        text = line
        alignment = "left"
        font_size = self.font_size

        while True:
            updated = False
            if text.startswith(ALIGN_CENTER_TOKEN):
                alignment = "center"
                text = text[len(ALIGN_CENTER_TOKEN):]
                updated = True
            elif text.startswith(ALIGN_RIGHT_TOKEN):
                alignment = "right"
                text = text[len(ALIGN_RIGHT_TOKEN):]
                updated = True
            elif text.startswith(ALIGN_LEFT_TOKEN):
                alignment = "left"
                text = text[len(ALIGN_LEFT_TOKEN):]
                updated = True
            elif text.startswith(SMALL_TEXT_TOKEN):
                font_size = self.font_size_small
                text = text[len(SMALL_TEXT_TOKEN):]
                updated = True

            if not updated:
                break

        return text, alignment, font_size

    def _get_font(self, size: int):
        if size in self._font_cache:
            return self._font_cache[size]
        try:
            font = ImageFont.truetype(str(self.font_path), size)
        except Exception as exc:
            LOGGER.exception("Failed to load font %s at size %s", self.font_path, size)
            raise RuntimeError("Failed to load Sarabun font") from exc
        self._font_cache[size] = font
        return font

    def print_image(self, path: str | Path) -> None:
        if not path:
            return
        image_path = get_real_path(path)
        if not image_path.exists():
            LOGGER.warning("Header image %s not found; skipping", path)
            return
        LOGGER.debug("Printing image %s", image_path)

        device = self.connect()

        if Image is None:  # Pillow not available; send raw file
            try:
                device.image(str(image_path))
            except Exception as exc:  # pragma: no cover - hardware specific
                LOGGER.exception("Failed to print image %s", image_path)
                raise RuntimeError("Failed to print header image") from exc
            return

        try:
            pil_image = Image.open(image_path)
        except Exception as exc:
            LOGGER.exception("Failed to open image %s", image_path)
            raise RuntimeError("Failed to open image for printing") from exc

        processed = self._prepare_bitmap(pil_image)

        try:
            device.image(processed, impl="bitImageColumn")
        except Exception as exc:  # pragma: no cover - hardware specific
            LOGGER.exception("Failed to print processed image %s", image_path)
            raise RuntimeError("Failed to print header image") from exc

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
            # Fallback if cashdraw method is missing or using a driver that doesn't support it
            # Standard ESC/POS kick drawer command: ESC p m t1 t2
            # m=0 (pin 2), m=1 (pin 5)
            # t1=25, t2=250 (pulse duration)
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
        except Exception as exc:  # pragma: no cover - hardware specific
            LOGGER.exception("Failed to feed printer %s lines", lines)
            raise RuntimeError("Failed to feed paper") from exc

    def disconnect(self) -> None:
        if not self.device:
            return
        close_fn = getattr(self.device, "close", None)
        if callable(close_fn):
            try:
                close_fn()
            except Exception:  # pragma: no cover - best-effort cleanup
                LOGGER.debug("Failed to close printer device", exc_info=True)
        self.device = None

    def _prepare_bitmap(self, image: "Image.Image"):
        if image.mode != "L":
            image = image.convert("L")

        if image.width == 0 or image.height == 0:
            raise RuntimeError("Image has invalid dimensions")

        scale_ratio = min(1.0, self.pixel_width / float(image.width))
        if scale_ratio != 1.0:
            new_width = max(1, int(image.width * scale_ratio))
            new_height = max(1, int(image.height * scale_ratio))
            image = image.resize((new_width, new_height), Image.LANCZOS)

        image = image.convert("1")

        if image.width < self.pixel_width:
            canvas = Image.new("1", (self.pixel_width, image.height), 1)
            x_offset = max(0, (self.pixel_width - image.width) // 2)
            canvas.paste(image, (x_offset, 0))
            image = canvas

        return image


__all__ = ["ReceiptPrinter"]
