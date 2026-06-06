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

    # Optional free-text fields
    rfid = data.get("rfid")
    data["rfid"] = "" if rfid is None else str(rfid)
    # Canonical key is "info_title"; still accept the legacy "info-title".
    info_title = data.get("info_title")
    if info_title is None:
        info_title = data.get("info-title")
    data["info_title"] = "" if info_title is None else str(info_title)
    data.pop("info-title", None)

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

    # Validate images
    images = data.get("images")
    if images is not None:
        if not isinstance(images, dict):
            raise ValueError("Field 'images' must be an object")
        sanitized_images: dict[str, dict[str, Any]] = {}
        for slot in ("header", "footer"):
            slot_value = images.get(slot)
            if slot_value is None:
                continue
            if not isinstance(slot_value, dict):
                raise ValueError(f"Field 'images.{slot}' must be an object")
            entry: dict[str, Any] = {}
            src = slot_value.get("src")
            if src is not None:
                entry["src"] = str(src)
            scale = slot_value.get("scale")
            if scale is not None:
                try:
                    scale_value = float(scale)
                except (ValueError, TypeError):
                    raise ValueError(f"Field 'images.{slot}.scale' must be a number")
                if not 0 <= scale_value <= 100:
                    raise ValueError(f"Field 'images.{slot}.scale' must be between 0 and 100")
                entry["scale"] = scale_value
            if entry:
                sanitized_images[slot] = entry
        data["images"] = sanitized_images
    else:
        data["images"] = {}

    return data


def apply_payload_images(layout: dict[str, Any], images: dict[str, Any] | None) -> None:
    """Overlay payload `images` onto a layout config dict (in place).

    Maps each slot to the layout keys the renderer already reads. Caller controls
    precedence by choosing when to call this relative to other overrides.
    """
    slot_keys = {
        "header": ("header_image", "header_image_scale"),
        "footer": ("footer_image", "footer_image_scale"),
    }
    for slot, (img_key, scale_key) in slot_keys.items():
        entry = (images or {}).get(slot) or {}
        if entry.get("src") is not None:
            layout[img_key] = entry["src"]
        if entry.get("scale") is not None:
            layout[scale_key] = entry["scale"]


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