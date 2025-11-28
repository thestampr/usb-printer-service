"""Utility helpers for formatting ESC/POS receipt content."""
from __future__ import annotations

import textwrap
from typing import Iterable, List

from config.settings import LAYOUT, PRINTER

ALIGN_LEFT_TOKEN = "<<L>>"
ALIGN_CENTER_TOKEN = "<<C>>"
ALIGN_RIGHT_TOKEN = "<<R>>"
SMALL_TEXT_TOKEN = "<<SM>>"

LINE_WIDTH = PRINTER.get("line_width", 32)
CURRENCY = LAYOUT.get("currency", "บาท")
VOLUME_UNIT = LAYOUT.get("volume_unit", "ลิตร")


def _ensure_width(width: int | None = None) -> int:
    return width or LINE_WIDTH


def wrap_text(text: str, width: int | None = None) -> List[str]:
    width = _ensure_width(width)
    return textwrap.wrap(text, width=width) or [""]


def add_line(text: str = "") -> str:
    return f"{text}\n"


def add_empty_line() -> str:
    return "\n"


def add_divider(char: str = "-", width: int | None = None) -> str:
    width = _ensure_width(width)
    divider_char = char or "-"
    return f"{divider_char * width}\n"


def align_left(text: str, width: int | None = None) -> str:
    return f"{ALIGN_LEFT_TOKEN}{text or ''}"


def align_right(text: str, width: int | None = None) -> str:
    return f"{ALIGN_RIGHT_TOKEN}{text or ''}"


def align_center(text: str, width: int | None = None) -> str:
    return f"{ALIGN_CENTER_TOKEN}{text or ''}"


def apply_small_font(text: str) -> str:
    return f"{SMALL_TEXT_TOKEN}{text or ''}"


def format_customer(name: str, code: str | None = None) -> str:
    blocks: List[str] = []
    if name:
        blocks.append(add_line(f"ชื่อลูกค้า: {name}"))
    if code:
        blocks.append(add_line(f"รหัสลูกค้า: {code}"))
    return "".join(blocks)


def format_item(name: str, price_per_liter: float, liters: float) -> str:
    lines: List[str] = []
    for wrapped in wrap_text(name):
        lines.append(add_line(wrapped))
    price_text = f"{liters:.2f} {VOLUME_UNIT} × {price_per_liter:.2f} {CURRENCY}"
    lines.append(add_line(price_text))
    subtotal = price_per_liter * liters
    lines.append(add_line(f"= {subtotal:.2f} {CURRENCY}"))
    return "".join(lines)


def format_total(value: float) -> str:
    label = "รวมทั้งหมด"
    amount = f"{value:.2f} {CURRENCY}"
    width = _ensure_width(None)
    spacing = width - len(label) - len(amount)
    spacing = max(1, spacing)
    return f"{label}{' ' * spacing}{amount}\n"


def join_blocks(blocks: Iterable[str]) -> str:
    return "".join(blocks)
