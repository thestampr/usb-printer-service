"""Command-line interface for printing fuel receipts without HTTP."""
from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path

from config import settings
from printer.driver import ReceiptPrinter
from printer.template import build_receipt_text, validate_payload


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="USB receipt printer CLI")
    parser.add_argument("--header-image", dest="header_image", help="Optional header image path")
    parser.add_argument("--header-title", dest="header_title", help="Optional header title override")
    parser.add_argument(
        "--header-description",
        dest="header_description",
        help="Optional header description override",
    )
    parser.add_argument("--receipt-title", dest="receipt_title", help="Optional receipt title override")
    parser.add_argument("--footer-label", dest="footer_label", help="Optional footer label override")
    parser.add_argument("--footer-image", dest="footer_image", help="Optional footer image path")
    parser.add_argument(
        "--payload",
        required=True,
        help="JSON payload string or path to JSON file matching the /print body",
    )
    parser.add_argument(
        "--port",
        help="Override printer queue as 'PORT:PRINTER_NAME' (e.g., USB001:XP-58)",
    )
    return parser.parse_args()


def load_payload(payload_arg: str) -> dict:
    path = Path(payload_arg)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse JSON file: {exc}") from exc
    try:
        return json.loads(payload_arg)
    except json.JSONDecodeError as exc:
        raise ValueError("Payload must be valid JSON or a readable JSON file path") from exc


def configure_printer(port_override: str | None) -> dict:
    printer_cfg = deepcopy(settings.PRINTER)
    if port_override:
        if ":" not in port_override:
            raise ValueError("Port override must follow 'PORT:NAME' format")
        port, name = port_override.split(":", 1)
        printer_cfg["usb_port"] = port or printer_cfg.get("usb_port")
        printer_cfg["usb_name"] = name or printer_cfg.get("usb_name")
    return printer_cfg


def build_layout(args: argparse.Namespace) -> dict:
    layout = deepcopy(settings.LAYOUT)
    overrides = {
        "header_image": args.header_image,
        "header_title": args.header_title,
        "header_description": args.header_description,
        "receipt_title": args.receipt_title,
        "footer_label": args.footer_label,
        "footer_image": args.footer_image,
    }
    for key, value in overrides.items():
        if value:
            layout[key] = value
    return layout


def main() -> int:
    args = parse_arguments()

    try:
        payload = load_payload(args.payload)
        validated = validate_payload(payload)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    layout = build_layout(args)

    try:
        printer_config = configure_printer(args.port)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    receipt_text = build_receipt_text(validated, layout)
    printer = ReceiptPrinter(printer_config)

    try:
        header_image = layout.get("header_image")
        footer_image = layout.get("footer_image")

        if header_image:
            printer.print_image(header_image)
        printer.print_text(receipt_text)
        if footer_image:
            printer.print_image(footer_image)
        printer.feed(2)
        printer.cut()
    except RuntimeError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        printer.disconnect()

    print("[OK] Receipt printed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
