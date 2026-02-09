"""Shared helpers for receipt payload validation and rendering."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from config.settings import (
    PRINTER as DEFAULT_PRINTER,
    LAYOUT as DEFAULT_LAYOUT
)
from printer import utils


def validate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    # Validate items
    if "items" not in payload or not isinstance(payload["items"], list) or not payload["items"]:
        raise ValueError("Field 'items' is required and must be a non-empty list")

    sanitized_items = []
    for item in payload["items"]:
        if not isinstance(item, dict):
            raise ValueError("Each item must be an object")
        name = item.get("name")
        amount = item.get("amount")
        quantity = item.get("quantity")
        if name is None or amount is None or quantity is None:
            raise ValueError("Each item requires 'name', 'amount', and 'quantity'")
        sanitized_items.append({
            "name": str(name),
            "amount": float(amount),
            "quantity": float(quantity),
        })

    data: dict[str, Any] = dict(payload)
    data["items"] = sanitized_items

    # Validate header_info
    header_info = data.get("header_info")
    if header_info is not None:
        if not isinstance(header_info, dict):
            raise ValueError("Field 'header_info' must be an object")
        sanitized_header: dict[str, str] = {}
        for key, value in header_info.items():
            sanitized_key = str(key)
            sanitized_value = "" if value is None else str(value)
            sanitized_header[sanitized_key] = sanitized_value
        data["header_info"] = sanitized_header
    else:
        data["header_info"] = {}

    # Validate footer_info
    footer_info = data.get("footer_info")
    if footer_info is not None:
        if not isinstance(footer_info, dict):
            raise ValueError("Field 'footer_info' must be an object")
        sanitized_footer: dict[str, str] = {}
        for key, value in footer_info.items():
            sanitized_key = str(key)
            sanitized_value = "" if value is None else str(value)
            sanitized_footer[sanitized_key] = sanitized_value
        data["footer_info"] = sanitized_footer
    else:
        data["footer_info"] = {}

    # Validate transaction_info
    transaction_info = data.get("transaction_info")
    if transaction_info is not None:
        if not isinstance(transaction_info, dict):
            raise ValueError("Field 'transaction_info' must be an object")
        sanitized_transaction: dict[str, float | None] = {}
        for key in ["received", "change", "discount", "total"]:
            value = transaction_info.get(key)
            if value is not None:
                try:
                    sanitized_transaction[key] = float(value)
                except (ValueError, TypeError):
                    raise ValueError(f"Field 'transaction_info.{key}' must be a number")
            else:
                sanitized_transaction[key] = None
        data["transaction_info"] = sanitized_transaction
    else:
        data["transaction_info"] = {}

    return data


def build_receipt_text(data: dict[str, Any], layout_overrides: dict[str, Any] | None = None) -> str:
    layout = deepcopy(DEFAULT_LAYOUT)
    if layout_overrides:
        layout.update({k: v for k, v in layout_overrides.items() if v is not None})

    blocks = []
    header_title = layout.get("header_title", "")
    header_description = layout.get("header_description", "")
    receipt_title = layout.get("receipt_title", "")
    footer_label = layout.get("footer_label", "")

    if header_title:
        blocks.append(utils.add_line(utils.align_center(header_title)))
        blocks.append(utils.add_empty_line())
    if header_description:
        blocks.append(utils.add_line(utils.apply_small_font(utils.align_center(header_description))))
        blocks.append(utils.add_empty_line())

    if receipt_title:
        blocks.append(utils.add_line(utils.align_center(receipt_title)))
        blocks.append(utils.add_empty_line())

    if transection := data.get("transection"):
        blocks.append(utils.add_line(f"Transection: {transection}"))
        blocks.append(utils.add_empty_line())

    customer_block = utils.format_customer(data["customer"].get("name"), data["customer"].get("code"))
    if customer_block:
        blocks.append(customer_block)
        blocks.append(utils.add_empty_line())

    blocks.append(utils.add_line("รายการ:"))

    for item in data["items"]:
        blocks.append(utils.format_item(item["name"], item["amount"], item["quantity"]))
        blocks.append(utils.add_divider())

    blocks.append(utils.format_total(data["total"]))

    if promotion := data.get("promotion"):
        blocks.append(utils.add_line(f"Promotion: {promotion}"))
    if points := data.get("points"):
        blocks.append(utils.add_line(f"Points Earned: {points}"))

    extras = data.get("extras") or {}
    if extras:
        for key, value in extras.items():
            entry = f"{key}: {value}".strip()
            for wrapped in utils.wrap_text(entry):
                blocks.append(utils.add_line(wrapped))

    if footer_label:
        blocks.append(utils.add_empty_line())
        blocks.append(utils.add_line(utils.align_center(footer_label)))

    return utils.join_blocks(blocks)

def build_info_page() -> str:
    """Build a simple printer settings info page."""
    blocks = []
    blocks.append(utils.add_line(utils.align_center("Test page")))
    blocks.append(utils.add_empty_line())

    printer_cfg = deepcopy(DEFAULT_PRINTER)
    for key, value in printer_cfg.items():
        blocks.append(utils.add_line(key, right_text=str(value)))

    return utils.join_blocks(blocks)