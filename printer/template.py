"""Shared helpers for receipt payload validation and rendering."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from config.settings import LAYOUT as DEFAULT_LAYOUT
from printer import utils


def validate_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

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

    data: Dict[str, Any] = dict(payload)
    data["items"] = sanitized_items

    customer = data.get("customer", {}) or {}
    data["customer"] = {
        "name": str(customer.get("name", "")),
        "code": customer.get("code"),
    }

    if data.get("total") is not None:
        data["total"] = float(data["total"])
    else:
        data["total"] = sum(item["amount"] * item["quantity"] for item in sanitized_items)

    if data.get("points") is not None:
        data["points"] = int(data["points"])

    if data.get("promotion") is not None:
        data["promotion"] = str(data["promotion"])

    if data.get("transection") is not None:
        data["transection"] = str(data["transection"])

    extras = data.get("extras")
    if extras is None:
        data["extras"] = {}
    else:
        if not isinstance(extras, dict):
            raise ValueError("Field 'extras' must be an object")
        sanitized_extras: Dict[str, str] = {}
        for key, value in extras.items():
            sanitized_key = str(key)
            sanitized_value = "" if value is None else str(value)
            sanitized_extras[sanitized_key] = sanitized_value
        data["extras"] = sanitized_extras

    return data


def build_receipt_text(data: Dict[str, Any], layout_overrides: Dict[str, Any] | None = None) -> str:
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
