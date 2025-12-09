"""Command-line interface for opening the cash drawer via USB."""
from __future__ import annotations

import argparse
import sys
from copy import deepcopy

from config import settings
from printer.driver import ReceiptPrinter


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="open-drawer", description="Cash drawer cli")
    parser.add_argument(
        "--port",
        help="Override printer queue as 'PORT:PRINTER_NAME' (e.g., USB001:XP-58)",
    )
    return parser.parse_args()


def configure_printer(port_override: str | None) -> dict:
    printer_cfg = deepcopy(settings.PRINTER)
    if port_override:
        if ":" not in port_override:
            raise ValueError("Port override must follow 'PORT:NAME' format")
        port, name = port_override.split(":", 1)
        printer_cfg["usb_port"] = port or printer_cfg.get("usb_port")
        printer_cfg["usb_name"] = name or printer_cfg.get("usb_name")
    return printer_cfg


def main() -> int:
    args = parse_arguments()

    try:
        printer_config = configure_printer(args.port)
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    
    printer = ReceiptPrinter(printer_config)
    try:
        printer.kick_drawer()
    except ValueError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1
    finally:
        printer.disconnect()
    print("[OK] Cash drawer opened successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
