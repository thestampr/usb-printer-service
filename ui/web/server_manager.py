"""Run the Flask service in-process for the config UI.

Instead of spawning ``printer --serve`` as a child, the server runs inside the
config-UI process via :func:`werkzeug.serving.make_server` on a daemon thread.
That means no external console window, and logs are captured directly by
:mod:`ui.web.log_bridge` for the in-app console. Closing the UI window keeps this
thread alive (the window hides to the tray); only Stop/Quit shuts it down.
"""

from __future__ import annotations

import logging
import socket
import threading
from typing import Any, Callable, Optional

from werkzeug.serving import make_server

from config import settings
from server.app import create_app
from ui.web import log_bridge

_LOGGER = logging.getLogger("printer.service")


def _port_in_use(host: str, port: int) -> bool:
    """True if something is already listening on the port.

    werkzeug enables ``allow_reuse_address``; on Windows SO_REUSEADDR lets a
    second server *steal* an in-use port instead of failing, so make_server
    can't be relied on to raise. A connect probe is the robust pre-flight.
    """
    probe_host = "127.0.0.1" if host in ("0.0.0.0", "", "::") else host
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((probe_host, int(port))) == 0


class ServerManager:
    """Owns the running werkzeug server + its serve thread (single instance)."""

    def __init__(self) -> None:
        self._server = None  # werkzeug BaseWSGIServer
        self._thread: Optional[threading.Thread] = None
        self._host: str = ""
        self._port: int = 0
        self._lock = threading.Lock()
        # Called with the new running state after a successful start/stop
        # (set by ui.web.app to show/hide the tray icon). Fired outside the lock.
        self.on_change: Optional[Callable[[bool], None]] = None

    def _notify(self, running: bool) -> None:
        cb = self.on_change
        if cb:
            try:
                cb(running)
            except Exception:
                pass

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def status(self) -> dict[str, Any]:
        running = self.is_running()
        return {
            "running": running,
            "host": self._host if running else None,
            "port": self._port if running else None,
        }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self.is_running():
                return {
                    "ok": False,
                    "error": "Service is already running",
                    "running": True,
                    "host": self._host,
                    "port": self._port,
                }

            settings.reload()  # pick up the latest *saved* host/port/debug
            svc = settings.get_all().get("SERVICE", {})
            host = svc.get("host", "0.0.0.0")
            port = int(svc.get("port", 5000))
            debug = bool(svc.get("debug", False))
            log_bridge.set_level(debug)

            if _port_in_use(host, port):
                msg = f"Port {port} is already in use"
                log_bridge.emit_lines([f"ERROR {msg}"])
                return {"ok": False, "error": msg}

            app = create_app()
            # Note: app.debug is intentionally left off — the "Debug Mode" toggle
            # controls log verbosity only, not Flask's interactive debugger.
            try:
                server = make_server(host, port, app, threaded=True)
            except OSError as exc:
                msg = (
                    f"Port {port} is already in use"
                    if getattr(exc, "errno", None) in (48, 98, 10048)
                    or "in use" in str(exc).lower()
                    else f"Could not start service: {exc}"
                )
                log_bridge.emit_lines([f"ERROR {msg}"])
                return {"ok": False, "error": msg}

            self._server = server
            self._host, self._port = host, port
            self._thread = threading.Thread(
                target=server.serve_forever, name="flask-service", daemon=True
            )
            self._thread.start()
            log_bridge.emit_lines([f" * Serving on http://{host}:{port}/ (in-process)"])
            result = {"ok": True, "host": host, "port": port}
        self._notify(True)
        return result

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self.is_running():
                self._server = None
                self._thread = None
                return {"ok": True, "stopped": False}
            try:
                self._server.shutdown()
                if self._thread:
                    self._thread.join(timeout=5)
                self._server.server_close()  # release the socket for an immediate restart
            except Exception as exc:  # pragma: no cover - defensive
                log_bridge.emit_lines([f"ERROR Failed to stop service: {exc}"])
            log_bridge.emit_lines([" * Service stopped"])
            self._server = None
            self._thread = None
            result = {"ok": True, "stopped": True}
        self._notify(False)
        return result


# Module-level singleton used by the bridge + tray.
manager = ServerManager()
