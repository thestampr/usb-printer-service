"""In-app update checker and launcher.

Detects whether a newer version is published on GitHub (by comparing the local
``VERSION`` file against the same file on the ``main`` branch) and launches a
detached helper that applies the update once the running app has exited.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

REPO = "thestampr/usb-printer-service"
BRANCH = "main"
# The contents API returns the current file; raw.githubusercontent.com is served
# via a CDN that caches for ~5 min, so a freshly pushed VERSION isn't seen right
# away (and the cache can't be busted with a query string). RAW is kept only as a
# fallback if the API is unavailable.
API_VERSION_URL = f"https://api.github.com/repos/{REPO}/contents/VERSION?ref={BRANCH}"
RAW_VERSION_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/VERSION"

# DETACHED_PROCESS so the launched updater survives this process exiting.
_DETACHED_PROCESS = getattr(subprocess, "DETACHED_PROCESS", 0x00000008)


def _root() -> Path:
    """Return the install root (the directory containing VERSION / setup.cmd)."""
    return Path(__file__).resolve().parent.parent


def get_current_version() -> str:
    """Read the locally installed version from the VERSION file."""
    try:
        return (_root() / "VERSION").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _read_version(url: str, accept: str, timeout: float) -> str:
    request = urllib.request.Request(
        url, headers={"User-Agent": "usb-printer-service-updater", "Accept": accept}
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8").strip()
    if body[:1] == "{":  # contents API returned JSON instead of raw -> decode it
        import base64
        import json

        return base64.b64decode(json.loads(body)["content"]).decode("utf-8").strip()
    return body


def get_latest_version(timeout: float = 6.0) -> str:
    """Fetch the latest published version string from GitHub.

    Prefers the contents API (always current); falls back to the raw CDN (which
    can be up to ~5 min stale after a push) if the API is unavailable.
    """
    try:
        return _read_version(API_VERSION_URL, "application/vnd.github.raw", timeout)
    except Exception:
        return _read_version(RAW_VERSION_URL, "*/*", timeout)


def _parse(version: str) -> tuple[int, int, int]:
    """Parse 'x.y.z' (tolerating a leading 'v' and trailing suffixes) into a tuple."""
    parts: list[int] = []
    for chunk in version.strip().lstrip("vV").split("."):
        digits = ""
        for ch in chunk:
            if ch.isdigit():
                digits += ch
            else:
                break
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])  # type: ignore[return-value]


def is_newer(remote: str, local: str) -> bool:
    """True when the remote version is strictly newer than the local one."""
    return _parse(remote) > _parse(local)


def is_dev_checkout() -> bool:
    """True when running from a git working copy.

    Updating in place would overwrite uncommitted local changes, so callers
    should warn before proceeding.
    """
    return (_root() / ".git").is_dir()


def check_for_update(timeout: float = 6.0) -> dict:
    """Return {'current', 'latest', 'available'}. Raises on network/parse errors."""
    current = get_current_version()
    latest = get_latest_version(timeout=timeout)
    return {"current": current, "latest": latest, "available": is_newer(latest, current)}


def launch_updater(relaunch: str = "none") -> None:
    """Launch the detached updater helper and return immediately.

    The caller should exit promptly afterwards; the helper waits for this
    process to terminate before touching any files.

    ``relaunch`` controls what the helper reopens when done: ``"ui"`` reopens the
    configuration window, anything else reopens nothing.
    """
    root = _root()
    src_helper = root / "bin" / "apply_update.bat"
    if not src_helper.exists():
        raise FileNotFoundError(f"Updater helper not found: {src_helper}")

    # Run from a temp copy so the helper can safely overwrite its own bin/ original.
    tmp_helper = Path(tempfile.gettempdir()) / "ups_apply_update.bat"
    shutil.copy2(src_helper, tmp_helper)

    subprocess.Popen(
        [
            "cmd", "/c", "start", "USB Printer Service Update", "/D", str(root),
            str(tmp_helper), str(root), str(os.getpid()), relaunch,
        ],
        creationflags=_DETACHED_PROCESS,
        close_fds=True,
    )
