from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class Item:
    name: str
    amount: float
    quantity: float

    @property
    def line_total(self) -> float:
        return self.amount * self.quantity

@dataclass
class PayloadInfo:
    # Required raw sections
    header_info: dict[str, Any]
    footer_info: dict[str, Any]
    items: list[Item]

    # Transaction-derived fields
    received: Optional[float] = None
    change: Optional[float] = None
    discount: Optional[float] = None
    total: Optional[float] = None

    created_at: datetime = field(default_factory=datetime.now)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "PayloadInfo":
        """Create PayloadInfo from a dictionary payload."""

        # validation
        if "items" not in payload:
            raise ValueError("Missing required key")
        
        # Check if payload is in legacy format
        if _is_legacy_format(payload):
            return cls.from_legacy_dict(payload)

        # parse items
        items = [
            Item(
                name=i["name"],
                amount=float(i["amount"]),
                quantity=float(i["quantity"]),
            )
            for i in payload["items"]
        ]

        items_total = sum(item.line_total for item in items)

        # transaction info
        tx = payload.get("transaction_info", {}) or {}

        received = _to_float_or_none(tx.get("received"))
        change = _to_float_or_none(tx.get("change"))
        discount = _to_float_or_none(tx.get("discount"))
        total = _to_float_or_none(tx.get("total"))

        # business rules
        # if total not supplied -> start from items total
        if total is None:
            total = items_total

        # if discount supplied -> apply it (discount expected positive)
        if discount is not None and total == items_total:
            total = items_total - discount

        # if received & change known -> authoritative total
        #    total = received - change
        if received is not None and change is not None:
            total = received - change

        # if received & total known -> compute change
        if received is not None and change is None:
            change = received - total

        # if change & total known -> compute received
        if change is not None and received is None:
            received = total + change

        # if received & change known but discount missing -> infer discount
        #    discount = total - items_total
        if received is not None and change is not None and discount is None:
            discount = items_total - total

        # footer Info population
        footer_info = payload.get("footer_info", {}) or {}
        if received is not None: footer_info["Received"] = received
        if change is not None: footer_info["Change"] = change
        if discount is not None: footer_info["Discount"] = discount

        return cls(
            header_info=payload["header_info"],
            footer_info=footer_info,
            items=items,
            received=received,
            change=change,
            discount=discount,
            total=total,
        )
    
    @classmethod
    def from_legacy_dict(cls, payload: dict[str, Any]) -> "PayloadInfo":
        """similar implementation as from_dict but for legacy formats"""

        new_payload = {}

        # Copy over customer info
        header_info: dict[str, Any] = {}
        if "customer" in payload:
            customer: dict[str, str] = payload["customer"]
            for key, value in customer.items():
                header_info[f"Customer {key.capitalize()}"] = value

        # Copy over transaction-related info to header
        if "transection" in payload:
            header_info["Transaction"] = payload["transection"]
        if "promotion" in payload:
            header_info["Promotion"] = payload["promotion"]
        new_payload["header_info"] = header_info

        # Copy over items
        new_payload["items"] = payload["items"]

        # Copy over footer info
        footer_info: dict[str, Any] = {}
        if "points" in payload:
            footer_info["Points"] = payload["points"]
        new_payload["footer_info"] = footer_info

        # Copy over transaction info
        tx_info = {}
        if "total" in payload:
            tx_info["total"] = payload["total"]
        if "extras" in payload:
            tx_info.update(payload["extras"])
        new_payload["transaction_info"] = tx_info

        return cls.from_dict(new_payload)


def _to_float_or_none(value) -> Optional[float]:
    if value is None:
        return None
    return float(value)

def _is_legacy_format(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ["customer", "transection", "promotion", "points", "extras"])