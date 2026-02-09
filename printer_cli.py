"""Command-line interface for printing fuel receipts."""

from __future__ import annotations

import argparse
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Optional

from config import settings
from printer.driver import ReceiptPrinter
from printer.renderer import generate_receipt_image
from printer.template import validate_payload
from server.app import create_app
from ui.main import main as launch_ui, print_preview
from common.interface import PayloadInfo


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="printer", 
        description="USB receipt printer CLI"
    )
    parser.add_argument(
        "--header-image", 
        dest="header_image", 
        help="Optional header image path"
    )
    parser.add_argument(
        "--header-title", 
        dest="header_title", 
        help="Optional header title override"
    )
    parser.add_argument(
        "--header-description",
        dest="header_description",
        help="Optional header description override",
    )
    parser.add_argument(
        "--receipt-title", 
        dest="receipt_title", 
        help="Optional receipt title override"
    )
    parser.add_argument(
        "--footer-label", 
        dest="footer_label", 
        help="Optional footer label override"
    )
    parser.add_argument(
        "--footer-image", 
        dest="footer_image", 
        help="Optional footer image path"
    )
    parser.add_argument(
        "--payload",
        required=False,
        help="JSON payload string or path to a JSON file matching the /print body",
    )
    parser.add_argument(
        "--port",
        help="Override printer queue as 'PORT:PRINTER_NAME' (e.g., USB001:XP-58)",
    )
    parser.add_argument(
        "--config",
        action="store_true",
        help="Open the configuration UI and exit",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Print a test page that summarizes the current printer settings",
    )
    parser.add_argument(
        "--serve",
        nargs="?",
        const="",
        help="Run the Flask API server (optionally specify host:port)",
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

def configure_printer(port_override: Optional[str]) -> dict:
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

def parse_serve_address(value: Optional[str]) -> tuple[str, int]:
    default_host = settings.SERVICE.get("host", "0.0.0.0")
    default_port = settings.SERVICE.get("port", 5000)

    if value in (None, ""): return default_host, default_port
    if ":" not in value: raise ValueError("--serve expects host:port")

    host, port_str = value.split(":", 1)
    host = host or default_host
    try:
        port = int(port_str)
    except ValueError as exc:
        raise ValueError("Port in --serve must be an integer") from exc
    if port <= 0 or port > 65535:
        raise ValueError("Port in --serve must be between 1 and 65535")
    return host, port


def main() -> int:
    args = parse_arguments()

    if args.config:
        launch_ui()
        return 0

    if args.serve is not None:
        try:
            host, port = parse_serve_address(args.serve)
        except ValueError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2

        app = create_app()
        debug = settings.SERVICE.get("debug", False)
        app.run(host=host, port=port, debug=debug)
        return 0

    if args.test:
        try:
            print_preview()
        except RuntimeError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

        print("[OK] Test page printed successfully")
        return 0

    if not args.payload:
        print("[ERROR] --payload is required unless --config or --test is used", file=sys.stderr)
        return 2

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

    info = PayloadInfo.from_dict(validated)
    img = generate_receipt_image(
        layout, 
        info
    )
    
    printer = ReceiptPrinter(printer_config)
    try:
        printer.print_image(img)
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
