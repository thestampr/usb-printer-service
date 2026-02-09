from __future__ import annotations

from typing import Optional, TypeVar

REF = Optional[TypeVar('REF')]
def keepref(name: str, value: REF = None) -> REF:
    if not hasattr(keepref, "ref"):
        keepref.ref = {}

    if value is not None: keepref.ref[name] = value

    if name in keepref.ref:
        return keepref.ref[name]
    return value

__all__ = [
    "keepref",
]