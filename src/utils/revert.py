"""Session manifest I/O and per-fix revert logic."""

from __future__ import annotations

import ctypes
import json
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from src.utils.action_logger import action_logger
from src.utils.formatting import print_error, print_info, print_warning
from src.utils.paths import get_session_backup_path

# Display constants (Windows API values — avoids importing from agent_tools)
_DM_PELSWIDTH = 0x00080000
_DM_PELSHEIGHT = 0x00100000
_DM_DISPLAYFREQUENCY = 0x00400000
_CDS_UPDATEREGISTRY = 1
_CDS_TEST = 0x00000002
_DISP_CHANGE_SUCCESSFUL = 0


# ---------------------------------------------------------------------------
# Manifest write / read
# ---------------------------------------------------------------------------
#
# Lifecycle -- one manifest per app session:
#
#   first fix (pipeline OR dashboard) --> lazy-create / flush staged manifest
#        |                                          |
#        v                                          v
#   accumulate every applied fix  ------------>  written to disk
#        |
#        v
#   explicit revert (run_revert_phase), on success --> manifest file deleted
#
# A second pipeline run does NOT reset the manifest: start_session_manifest is
# a no-op while one is active, so revert can undo every run's changes.
# See docs/pipeline-rescan-idempotency-plan.md.


_pending_manifest: dict | None = None

# Serializes every read-modify-write of the manifest. The pipeline runs on a
# QThread and a dashboard monitor-fix runs on its own QThread; both append to
# the same manifest, so the read-modify-write must not interleave.
_manifest_lock = threading.Lock()


def _new_manifest(restore_point_created: bool) -> dict:
    """Build a fresh, empty session manifest."""
    return {
        "schema_version": 1,
        "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "session_date": datetime.now().isoformat(),
        "restore_point_created": restore_point_created,
        "fixes": [],
    }


def start_session_manifest(restore_point_created: bool = False) -> None:
    """Stage a session manifest in memory, only if none is active yet.

    The manifest spans one app session: it accumulates every applied fix
    until an explicit revert deletes it. Calling this again while a manifest
    is already active -- staged in memory or written to disk -- is a no-op,
    so re-running the pipeline never discards the earlier run's revert data.

    Written to disk only when the first fix is applied (see
    ``append_fix_to_manifest``); a run that applies nothing leaves no file.
    """
    global _pending_manifest
    with _manifest_lock:
        if _pending_manifest is not None or _read_raw_manifest() is not None:
            return  # a session manifest is already active
        _pending_manifest = _new_manifest(restore_point_created)


def mark_restore_point_created() -> None:
    """Record that a System Restore Point now exists for this session.

    Called by ``BootstrapPhase`` after the restore point is created. If a
    manifest was lazily created earlier by a dashboard fix -- with
    ``restore_point_created=False`` because no restore point existed yet --
    this upgrades the flag so revert can honestly offer System Restore.
    A no-op when no manifest exists; the pipeline's first fix will then stage
    one with the correct value.
    """
    global _pending_manifest
    with _manifest_lock:
        if _pending_manifest is not None:
            _pending_manifest["restore_point_created"] = True
            return
        manifest = _read_raw_manifest()
        if manifest is not None:
            manifest["restore_point_created"] = True
            _write_manifest(manifest)


def append_fix_to_manifest(entry: dict) -> None:
    """Append one applied-fix entry to the session manifest.

    Flushes the staged in-memory manifest to disk on the first call, then
    reads-appends-writes on subsequent calls. The manifest accumulates across
    the whole session and is never archived -- an explicit revert is what
    clears it. If no manifest is active (e.g. a dashboard fix is the first
    action of the session, before any pipeline run), one is created lazily
    with ``restore_point_created=False`` -- no restore point exists outside
    the pipeline.
    """
    global _pending_manifest
    with _manifest_lock:
        try:
            if _pending_manifest is not None:
                manifest = _pending_manifest
                _pending_manifest = None
            else:
                manifest = _read_raw_manifest()
            if manifest is None:
                # Lazy creation: a dashboard-initiated fix with no pipeline
                # run before it. No restore point exists outside the pipeline.
                manifest = _new_manifest(restore_point_created=False)
            manifest.setdefault("fixes", []).append(entry)
            _write_manifest(manifest)
        except Exception as e:
            prefix = entry.get("fix", "unknown")
            print_warning(f"[{prefix}] Fix applied but revert log failed: {e}")


def load_manifest() -> dict | None:
    """Return the session manifest, or None if not found or corrupt."""
    with _manifest_lock:
        data = _read_raw_manifest()
    if data is not None:
        ver = data.get("schema_version")
        if ver is None or ver != 1:
            print_warning(f"Session manifest has unexpected schema_version={ver!r}; proceeding anyway.")
    return data


# ---------------------------------------------------------------------------
# Revert execution
# ---------------------------------------------------------------------------


def revert_fix(entry: dict) -> tuple[bool, str]:
    """Dispatch revert for a single fix entry.

    Returns (success, error_message).  Empty error_message means success.
    """
    fix_key = entry.get("fix", "")
    try:
        if fix_key == "power_plan":
            return _revert_power_plan(entry)
        if fix_key == "game_mode":
            return _revert_game_mode(entry)
        if fix_key == "nvidia_profile":
            return _revert_nvidia_profile(entry)
        if fix_key == "display":
            return _revert_display(entry)
        return False, f"No revert handler for '{fix_key}'"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def trigger_system_restore(session_date: str) -> bool:
    """Launch Windows System Restore UI and direct the user to the lil_bro restore point.

    Returns True if rstrui.exe launched, False on failure.
    """
    try:
        subprocess.Popen(["rstrui.exe"])
        print_info("Windows System Restore has opened.")
        print_info("Select the restore point labelled:")
        print_info(f"  'lil_bro Pre-Tuning {session_date}'")
        print_info("and follow the prompts to roll back your system.")
        return True
    except Exception as exc:  # noqa: BLE001
        print_error(f"Could not launch System Restore: {exc}")
        print_info("Run rstrui.exe manually from Start to access System Restore.")
        return False


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _read_raw_manifest() -> dict | None:
    """Read manifest from disk. Returns None on missing file or JSON error."""
    path = get_session_backup_path()
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print_warning(f"Session backup is corrupt ({path}). Treating as empty.")
        return None
    except OSError:
        return None


def _write_manifest(manifest: dict) -> None:
    """Serialize and write manifest to disk. Logs warning on failure."""
    path = get_session_backup_path()
    try:
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    except OSError as exc:
        print_warning(
            "Revert will not be available for this session — backup could not be saved."
        )
        action_logger.log_action("Revert", "Manifest write failed", str(exc), outcome="WARN")


# ---------------------------------------------------------------------------
# Per-fix revert implementations
# ---------------------------------------------------------------------------


def _revert_power_plan(entry: dict) -> tuple[bool, str]:
    from src.agent_tools.power_plan import set_active_plan

    before = entry.get("before", {})
    guid = before.get("guid")
    if not guid:
        return False, "power_plan revert: missing before.guid"
    try:
        set_active_plan(guid)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _revert_game_mode(entry: dict) -> tuple[bool, str]:
    from src.agent_tools.game_mode import set_game_mode

    before = entry.get("before", {})
    value = before.get("AutoGameModeEnabled")
    if value is None:
        return False, "game_mode revert: missing before.AutoGameModeEnabled"
    try:
        set_game_mode(enabled=bool(value))
        action_logger.log_action(
            "Revert",
            f"Game Mode restored to AutoGameModeEnabled={value}",
            r"HKCU\SOFTWARE\Microsoft\GameBar",
        )
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def _revert_nvidia_profile(entry: dict) -> tuple[bool, str]:
    from src.agent_tools.nvidia_profile_setter import apply_nvidia_profile
    from src.utils.nvidia_npi import find_npi_exe

    backup_path = entry.get("before_backup")
    if not backup_path:
        return False, "nvidia_profile revert: missing before_backup path"
    if not Path(backup_path).exists():
        return False, f"nvidia_profile revert: backup not found at {backup_path}"

    npi_exe = find_npi_exe()
    if npi_exe is None:
        return False, "nvidia_profile revert: NPI.exe not found"

    ok, msg = apply_nvidia_profile(npi_exe, backup_path)
    if ok:
        action_logger.log_action("Revert", "NVIDIA profile restored", backup_path)
    return ok, msg


def _revert_display(entry: dict) -> tuple[bool, str]:
    from src.utils.display_utils import DEVMODE

    before = entry.get("before", {})
    device = before.get("device")
    width = before.get("width")
    height = before.get("height")
    hz = before.get("hz")

    if not all(v is not None for v in [device, width, height, hz]):
        return False, "display revert: incomplete before state (device/width/height/hz required)"

    if not isinstance(device, str) or not device:
        return False, "display revert: device must be a non-empty string"
    if not all(isinstance(v, int) and v > 0 for v in [width, height, hz]):
        return False, "display revert: width/height/hz must be positive integers"

    mode = DEVMODE()
    mode.dmSize = ctypes.sizeof(DEVMODE)
    mode.dmFields = _DM_PELSWIDTH | _DM_PELSHEIGHT | _DM_DISPLAYFREQUENCY
    mode.dmPelsWidth = width
    mode.dmPelsHeight = height
    mode.dmDisplayFrequency = hz

    test_result = ctypes.windll.user32.ChangeDisplaySettingsExW(
        device, ctypes.byref(mode), None, _CDS_TEST, None
    )
    if test_result != _DISP_CHANGE_SUCCESSFUL:
        return False, f"display revert validation failed (CDS_TEST returned {test_result})"

    result = ctypes.windll.user32.ChangeDisplaySettingsExW(
        device, ctypes.byref(mode), None, _CDS_UPDATEREGISTRY, None
    )
    if result == _DISP_CHANGE_SUCCESSFUL:
        action_logger.log_action(
            "Revert", f"Display restored to {width}x{height}@{hz}Hz", device
        )
        return True, ""
    if result == 1:  # DISP_CHANGE_RESTART
        action_logger.log_action(
            "Revert", f"Display restored to {width}x{height}@{hz}Hz (reboot required)", device
        )
        return True, "reboot required to apply display change"
    return False, f"ChangeDisplaySettingsExW returned {result} for {device}"
