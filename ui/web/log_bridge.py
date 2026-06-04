"""Capture service logs and fan them out to the in-app console.

The Flask service runs in-process (see :mod:`ui.web.server_manager`), so its
werkzeug/app logs are captured with a :class:`logging.Handler` rather than read
from a file. Lines are kept in a bounded ring buffer (so the Service tab can be
re-seeded with history when it attaches) and pushed live to a swappable *sink*
(the UI wires this to ``window.evaluate_js("App.service._push(...)")``).
"""

from __future__ import annotations

import logging
import threading
from collections import deque
from typing import Callable, List, Optional

# Bounded history so a long-running service can't grow memory without bound.
_RING: deque[str] = deque(maxlen=500)
_LOCK = threading.Lock()
_SINK: Optional[Callable[[List[str]], None]] = None

# Scope to the service's own loggers — NOT root — so third-party DEBUG spam
# (PIL, urllib3, etc.) never leaks into the console even in debug mode.
_LOGGERS = ("werkzeug", "flask.app", "printer")
_handler: Optional["ConsoleHandler"] = None


def set_sink(sink: Optional[Callable[[List[str]], None]]) -> None:
    """Set (or clear) the live sink that receives new log lines."""
    global _SINK
    _SINK = sink


def history() -> List[str]:
    """Snapshot of the buffered lines, oldest first."""
    with _LOCK:
        return list(_RING)


def emit_lines(lines: List[str]) -> None:
    """Record lines in the ring and forward them to the sink (used by the handler
    and by the server manager for its own synthetic banner/status lines)."""
    if not lines:
        return
    with _LOCK:
        _RING.extend(lines)
    sink = _SINK
    if sink is not None:
        try:
            sink(lines)
        except Exception:
            # The console is best-effort; never let UI delivery break logging.
            pass


class ConsoleHandler(logging.Handler):
    """Routes log records to :func:`emit_lines`.

    werkzeug request records are emitted as their raw message (e.g.
    ``'127.0.0.1 - - [..] "GET /health HTTP/1.1" 200 -'``) so the JS colorizer's
    HTTP regex matches; everything else is prefixed with its level name.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            if record.name == "werkzeug":
                text = record.getMessage()
            else:
                text = f"{record.levelname} {record.getMessage()}"
            emit_lines(text.splitlines() or [""])
        except Exception:  # pragma: no cover - defensive
            self.handleError(record)


def install(debug: bool = False) -> None:
    """Attach the console handler to the service loggers (idempotent)."""
    global _handler
    if _handler is None:
        _handler = ConsoleHandler()
    set_level(debug)
    for name in _LOGGERS:
        logger = logging.getLogger(name)
        if _handler not in logger.handlers:
            logger.addHandler(_handler)
        # Captured directly here; don't also bubble to the root logger.
        logger.propagate = False


def set_level(debug: bool) -> None:
    """Map the Service "Debug Mode" toggle to console verbosity."""
    level = logging.DEBUG if debug else logging.INFO
    if _handler is not None:
        _handler.setLevel(level)
    for name in _LOGGERS:
        logging.getLogger(name).setLevel(level)
