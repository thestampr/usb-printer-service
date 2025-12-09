"""JSON-backed configuration for the USB receipt printer service."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

_CONFIG_FILE = Path(__file__).with_name("temp.settings.json")

_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "PRINTER": {
        "usb_port": "USB001",
        "usb_name": "XP-58",
        "encoding": "utf-8",
        "line_width": 44,
        "pixel_width": 384
    },
    "LAYOUT": {
        "header_image": "",
        "header_title": "Your Gas Station",
        "header_description": "Your Address Here",
        "receipt_title": "Receipt title",
        "footer_label": "Thank you!",
        "footer_image": "",
        "font_family": "Sarabun-SemiBold",
        "font_path": "assets/fonts/Sarabun/Sarabun-SemiBold.ttf",
        "font_size": 24,
        "font_size_small": 20,
        "line_spacing": 6,
        "currency": "bth",
        "volume_unit": "liters"
    },
    "SERVICE": {
        "host": "0.0.0.0",
        "port": 5000,
        "debug": True
    }
}

_DATA: Dict[str, Dict[str, Any]] = {}


def _ensure_config_file() -> None:
    if not _CONFIG_FILE.exists():
        _write_config(_DEFAULTS)


def _merge_with_defaults(raw: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for section, defaults in _DEFAULTS.items():
        section_values: Dict[str, Any] = deepcopy(defaults)
        incoming = raw.get(section)
        if isinstance(incoming, dict):
            section_values.update(incoming)
        merged[section] = section_values
    return merged


def _load_config() -> Dict[str, Dict[str, Any]]:
    _ensure_config_file()
    with _CONFIG_FILE.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    return _merge_with_defaults(raw)


def _write_config(data: Dict[str, Dict[str, Any]]) -> None:
    with _CONFIG_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def _refresh_globals(new_data: Dict[str, Dict[str, Any]]) -> None:
    global PRINTER, LAYOUT, SERVICE, _DATA
    _DATA = deepcopy(new_data)
    PRINTER = deepcopy(_DATA["PRINTER"])
    LAYOUT = deepcopy(_DATA["LAYOUT"])
    SERVICE = deepcopy(_DATA["SERVICE"])


def reload() -> None:
    """Reload settings from disk."""
    config = _load_config()
    _refresh_globals(config)


def get_all() -> Dict[str, Dict[str, Any]]:
    """Return a copy of the full configuration tree."""
    return deepcopy(_DATA)


def get_defaults() -> Dict[str, Dict[str, Any]]:
    """Return a copy of the default configuration values."""
    return deepcopy(_DEFAULTS)


def save_all(data: Dict[str, Dict[str, Any]]) -> None:
    """Persist the provided configuration tree and refresh module globals."""
    merged = _merge_with_defaults(data)
    _write_config(merged)
    _refresh_globals(merged)


def update_section(section: str, values: Dict[str, Any]) -> None:
    """Update a specific configuration section and persist it."""
    current = get_all()
    if section not in current:
        raise KeyError(f"Unknown settings section: {section}")
    current[section].update(values)
    save_all(current)


reload()

__all__ = [
    "PRINTER",
    "LAYOUT",
    "SERVICE",
    "reload",
    "get_all",
    "get_defaults",
    "save_all",
    "update_section",
]
