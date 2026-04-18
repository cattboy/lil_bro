"""Session manifest I/O and per-fix revert logic."""

from __future__ import annotations

import ctypes
import json
import subprocess
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


def start_session_manifest(restore_point_created: bool = True) -> None:
    """Write a fresh manifest at the start of each run.

    Overwrites the previous session — not called at exit, so a crash does not
    destroy the last good backup.  On write failure, logs a warning and
    continues; the fix run proceeds regardless.
    """
    session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    manifest: dict = {
        "schema_version": 1,
        "session_id": session_id,
        "session_date": datetime.now().isoformat(),
        "restore_point_created": restore_point_created,
        "fixes": [],
    }
    old_path = get_session_backup_path()
    if old_path.exists():
        try:
            import json as _json
            old_data = _json.loads(old_path.read_text(encoding="utf-8"))
            old_id = old_data.get("session_id", "unknown")
            old_path.rename(old_path.parent / f"session_{old_id}.json")
        except Exception:
            pass
    _write_manifest(manifest)


def append_fix_to_manifest(entry: dict) -> None:
    """Append one fix entry to the session manifest.

    Called by each fix wrapper *after* applying the fix, so the revert
    metadata reflects the actual outcome.  On any failure the fix result
    is unaffected.
    """
    manifest = _read_raw_manifest()
    if manifest is None:
        print_warning("Revert manifest missing — this fix will not be revertible.")
        return
    manifest.setdefault("fixes", []).append(entry)
    _write_manifest(manifest)


def load_manifest() -> dict | None:
    """Return the session manifest, or None if not found or corrupt."""
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
    from src.collectors.sub.nvidia_profile_dumper import find_npi_exe

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
