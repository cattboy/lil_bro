"""PawnIO ownership marker — records that *this* lil_bro install put PawnIO on the box.

`post_run_cleanup._uninstall_pawnio` must never remove a PawnIO that lil_bro did not
install (another app such as HWiNFO or LibreHardwareMonitor may own it). Within a
single run that is decided by ``pawnio_was_preinstalled`` (a registry snapshot taken
at startup). This module carries that ownership *across* runs.

Ownership is decided by **boot-session gating**, not by driver fingerprint. The only
legitimate leftover is a ``sc delete`` that returned 1072 (marked-for-deletion) which
completes at the next reboot. So a real lil_bro leftover can only exist within the same
boot session: a marker written before the last boot is stale (its pending deletion has
already completed) and any PawnIO present after a reboot is provably not our zombie.
Fingerprint matching (oem inf / Driver Store hash) is unsound here — identical PawnIO
builds share the Driver Store hash, so a match cannot prove *we* installed it.

The marker is a small JSON file at the CWD root (beside ``lil_bro_actions.log``), so it
survives the ``./lil_bro/`` cleanup. Steady state after a clean removal leaves no
marker — it persists only while a removal is incomplete, exactly when it is needed.

All functions are best-effort and never raise: a marker problem must not break cleanup.
"""

import json
from datetime import datetime, timedelta

from .debug_logger import get_debug_logger
from .paths import get_pawnio_owned_marker_path

_INSTALLED_AT = "installed_at"


def mark_pawnio_owned() -> None:
    """Record that lil_bro installed PawnIO this run (idempotent; never raises)."""
    try:
        from src._version import __version__
    except Exception:
        __version__ = "unknown"
    payload = {
        "installed_by": "lil_bro",
        "version": __version__,
        _INSTALLED_AT: datetime.now().isoformat(),
    }
    try:
        with open(get_pawnio_owned_marker_path(), "w", encoding="utf-8") as f:
            json.dump(payload, f)
    except OSError:
        get_debug_logger().warning("Failed to write PawnIO ownership marker", exc_info=True)


def read_pawnio_owned_marker() -> "dict | None":
    """Return the parsed marker dict, or None if absent/unreadable (never raises)."""
    path = get_pawnio_owned_marker_path()
    try:
        if not path.is_file():
            return None
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def clear_pawnio_owned_marker() -> None:
    """Delete the marker if present (never raises)."""
    try:
        get_pawnio_owned_marker_path().unlink(missing_ok=True)
    except OSError:
        get_debug_logger().warning("Failed to clear PawnIO ownership marker", exc_info=True)


def _last_boot_time() -> datetime:
    """Wall-clock time of the last boot, derived from system uptime.

    Uses ``GetTickCount64`` (milliseconds since boot) via ctypes — no subprocess, no
    extra dependency. On any failure returns ``datetime.max`` so that
    ``marker_is_current_boot`` is False (the safe answer: never treat a marker as
    current-boot, hence never remove a possibly third-party driver).
    """
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.GetTickCount64.restype = ctypes.c_uint64
        uptime_ms = int(kernel32.GetTickCount64())
        return datetime.now() - timedelta(milliseconds=uptime_ms)
    except Exception:
        return datetime.max


def marker_is_current_boot() -> bool:
    """True iff a marker exists and was written during the current boot session.

    This is the cross-run ownership signal: a marker older than the last boot is stale
    (its pending deletion completed at that reboot) and must not be trusted.
    """
    marker = read_pawnio_owned_marker()
    if not marker:
        return False
    raw = marker.get(_INSTALLED_AT)
    if not raw:
        return False
    try:
        installed_at = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return False
    return installed_at > _last_boot_time()
