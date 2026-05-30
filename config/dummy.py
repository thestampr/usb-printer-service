"""JSON-backed example (dummy) payload used for the live preview and test print.

The dummy payload is editable from the configuration UI's "Dummy" panel and is
persisted to ``config/temp.dummy.json`` (ignored by git, preserved across updates).
When the file is missing or unreadable, the built-in :data:`DEFAULT_DUMMY` is used.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

_DUMMY_FILE = Path(__file__).with_name("temp.dummy.json")

# A full example payload that exercises every supported data field. `header_info`
# lists all the recognized (auto-translated) keys; `transaction_info` carries all
# four keys with self-consistent values (received - change == total). Header/footer
# images are intentionally omitted — they are configured in the UI's Layout tab,
# which the preview and test print already source images from.
DEFAULT_DUMMY: dict[str, Any] = {
    "rfid": "",
    "info-title": "Tax Invoice (ABB)",
    "header_info": {
        "No.": "00123",
        "Customer Name": "Dummy",
        "Customer Code": "CT-9904",
        "Transaction": "TXN-TEST-1234",
        "Promotion": "TestOnProd",
        "Date": "2026-05-30",
        "Time": "14:35",
        "Cashier": "Alice",
        "Address": "123 Rama 4 Rd, Bangkok",
        "Tax ID": "0105500000001",
        "Tax ID Customer": "1234567890123",
        "Branch": "00001",
        "Car Plate": "1กก 1234",
    },
    "items": [
        {
            "name": "Gasoline 95",
            "amount": 40.5,
            "quantity": 30,
        },
        {
            "name": "Water Bottle",
            "amount": 10.0,
            "quantity": 1,
        },
    ],
    "footer_info": {
        "Points": "150",
    },
    "transaction_info": {
        "received": 1500.0,
        "change": 300.0,
        "discount": 25.0,
        "total": 1200.0,
    },
}


def load() -> dict[str, Any]:
    """Return the saved dummy payload, falling back to the built-in default."""
    if _DUMMY_FILE.exists():
        try:
            with _DUMMY_FILE.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, OSError):
            pass
    return deepcopy(DEFAULT_DUMMY)


def save(data: dict[str, Any]) -> None:
    """Persist the provided dummy payload to disk."""
    with _DUMMY_FILE.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def get_defaults() -> dict[str, Any]:
    """Return a copy of the built-in default dummy payload."""
    return deepcopy(DEFAULT_DUMMY)
