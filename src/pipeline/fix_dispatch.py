"""
Fix dispatch registry -- maps check names to executable fix functions.

Each fix handler has the signature: (specs: dict) -> bool
To add a new auto-fixable check, decorate the handler with @register_fix("check_name").
"""

from collections.abc import Callable

from datetime import datetime
from src.utils.action_logger import action_logger
from src.utils.formatting import print_error, print_success, print_warning

FIX_REGISTRY: dict[str, Callable[[dict], bool]] = {}


def register_fix(check_name: str) -> Callable:
    """Decorator that registers a fix handler under the given check name."""
    def decorator(fn: Callable[[dict], bool]) -> Callable[[dict], bool]:
        FIX_REGISTRY[check_name] = fn
        return fn
    return decorator


@register_fix("display")
def _fix_display(specs: dict) -> bool:
    """Sets monitor to highest available refresh rate."""
    from src.agent_tools.display_setter import apply_display_mode, find_best_mode, get_current_display_mode
    from src.collectors.sub.monitor_dumper import get_all_displays
    from src.utils.revert import append_fix_to_manifest

    try:
        devices = get_all_displays()
        device = devices[0] if devices else "\\\\.\\DISPLAY1"

        current = get_current_display_mode(device)
        if current is not None:
            before_state: dict | None = {
                "device": device,
                "width": current.dmPelsWidth,
                "height": current.dmPelsHeight,
                "hz": current.dmDisplayFrequency,
            }
        else:
            before_state = None

        mode = find_best_mode(device, target_hz=None, require_same_resolution=True)
        if mode is None:
            print_error("[display] No suitable mode found -- nothing changed.")
            return False

        ok, msg = apply_display_mode(device, mode, persist=True, dry_run=True)
        if not ok:
            print_error(f"[display] Validation failed: {msg}")
            return False

        ok, msg = apply_display_mode(device, mode, persist=True, dry_run=False)
        if not ok:
            print_error(f"[display] Apply failed: {msg}")
            return False
    except Exception as e:
        print_error(f"[display] Error: {e}")
        return False

    try:
        if before_state:
            append_fix_to_manifest({
                "fix": "display",
                "revertible": True,
                "before": before_state,
                "after": {
                    "device": device,
                    "width": mode.dmPelsWidth,
                    "height": mode.dmPelsHeight,
                    "hz": mode.dmDisplayFrequency,
                },
                "applied_at": datetime.now().isoformat(),
            })
        else:
            print_warning("[display] Could not capture before-state — fix will not be revertible.")
            append_fix_to_manifest({
                "fix": "display",
                "revertible": False,
                "reason": "Before-state not available",
                "applied_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print_warning(f"[display] Fix applied but revert log failed: {e}")

    print_success(
        f"[display] Refresh rate set to {mode.dmDisplayFrequency}Hz "
        f"({mode.dmPelsWidth}x{mode.dmPelsHeight}). {msg}"
    )
    return True


@register_fix("power_plan")
def _fix_power_plan(specs: dict) -> bool:
    """Switches to a high-performance power plan."""
    from src.agent_tools.power_plan import (
        _PERF_GUIDS,
        create_high_performance_plan,
        list_available_plans,
        set_active_plan,
    )
    from src.utils.revert import append_fix_to_manifest

    power_plan_spec = specs.get("PowerPlan", {})
    before_guid = power_plan_spec.get("guid")
    before_name = power_plan_spec.get("name")

    try:
        plans = list_available_plans()
        target = next((p for p in plans if p[0] in _PERF_GUIDS), None)
        if not target:
            target = next(
                (p for p in plans if "performance" in p[1].lower()), None
            )
        if target:
            guid, name = target
        else:
            guid, name = create_high_performance_plan()

        set_active_plan(guid)
    except Exception as e:
        print_error(f"[power_plan] Failed: {e}")
        return False

    try:
        if before_guid:
            append_fix_to_manifest({
                "fix": "power_plan",
                "revertible": True,
                "before": {"guid": before_guid, "name": before_name},
                "after": {"guid": guid, "name": name},
                "applied_at": datetime.now().isoformat(),
            })
        else:
            print_warning("[power_plan] Could not capture before-state — fix will not be revertible.")
            append_fix_to_manifest({
                "fix": "power_plan",
                "revertible": False,
                "reason": "Before-state not available in specs",
                "applied_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print_warning(f"[power_plan] Fix applied but revert log failed: {e}")

    print_success(f"[power_plan] Switched to '{name}'.")
    return True


@register_fix("temp_folders")
def _fix_temp_folders(specs: dict) -> bool:
    """Cleans temporary file directories."""
    from src.agent_tools.temp_audit import clean_temp_folders
    from src.utils.revert import append_fix_to_manifest

    details = specs.get("TempFolders", {}).get("details", {})

    try:
        clean_temp_folders(details)
    except Exception as e:
        print_error(f"[temp_folders] Cleanup failed: {e}")
        return False

    try:
        append_fix_to_manifest({
            "fix": "temp_folders",
            "revertible": False,
            "reason": "Deleted temp files cannot be restored",
            "display": "temp files deleted — files gone",
            "applied_at": datetime.now().isoformat(),
        })
    except Exception as e:
        print_warning(f"[temp_folders] Fix applied but revert log failed: {e}")

    return True


@register_fix("game_mode")
def _fix_game_mode(specs: dict) -> bool:
    """Enables Windows Game Mode via registry."""
    from src.agent_tools.game_mode import set_game_mode
    from src.utils.revert import append_fix_to_manifest

    game_mode_spec = specs.get("GameMode", {})
    before_enabled = game_mode_spec.get("enabled")

    try:
        ok = set_game_mode(enabled=True)
        if not ok:
            print_error("[game_mode] set_game_mode returned False.")
            return False
    except Exception as e:
        print_error(f"[game_mode] Failed: {e}")
        return False

    try:
        if before_enabled is not None:
            append_fix_to_manifest({
                "fix": "game_mode",
                "revertible": True,
                "before": {"AutoGameModeEnabled": 0 if not before_enabled else 1},
                "after": {"AutoGameModeEnabled": 1},
                "applied_at": datetime.now().isoformat(),
            })
        else:
            print_warning("[game_mode] Could not capture before-state — fix will not be revertible.")
            append_fix_to_manifest({
                "fix": "game_mode",
                "revertible": False,
                "reason": "Before-state not available in specs",
                "applied_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print_warning(f"[game_mode] Fix applied but revert log failed: {e}")

    print_success("[game_mode] Game Mode enabled.")
    return True


@register_fix("nvidia_profile")
def _fix_nvidia_profile(specs: dict) -> bool:
    """Applies optimized NVIDIA driver profile via NPI."""
    from src.agent_tools.nvidia_profile_setter import backup_nvidia_profile, fix_nvidia_profile
    from src.collectors.sub.nvidia_profile_dumper import find_npi_exe
    from src.utils.revert import append_fix_to_manifest

    npi_exe = find_npi_exe()
    backup_path: str | None = None
    if npi_exe is not None:
        try:
            backup_path = backup_nvidia_profile(npi_exe)
        except Exception as e:
            print_warning(f"[nvidia_profile] Backup failed ({e}) — fix will not be revertible.")
            backup_path = None
    else:
        print_warning("[nvidia_profile] NPI.exe not found — fix will not be revertible.")

    try:
        fix_nvidia_profile(specs, pre_backup_path=backup_path)
    except FileNotFoundError as e:
        print_error(f"[nvidia_profile] {e}")
        return False
    except Exception as e:
        print_error(f"[nvidia_profile] Failed: {e}")
        return False

    try:
        if backup_path is not None:
            append_fix_to_manifest({
                "fix": "nvidia_profile",
                "revertible": True,
                "before_backup": backup_path,
                "applied_at": datetime.now().isoformat(),
            })
        else:
            append_fix_to_manifest({
                "fix": "nvidia_profile",
                "revertible": False,
                "reason": "NPI.exe unavailable or backup failed",
                "applied_at": datetime.now().isoformat(),
            })
    except Exception as e:
        print_warning(f"[nvidia_profile] Fix applied but revert log failed: {e}")

    print_success(
        "[nvidia_profile] NVIDIA driver profile optimized "
        "(G-Sync, VSync, FPS cap, DLSS, power management)."
    )
    return True


def execute_fix(check: str, specs: dict) -> bool:
    """
    Executes the auto-fix for a given check name.

    Looks up the check in FIX_REGISTRY and calls the handler.
    Returns True on success, False if the check is unknown or the fix fails.
    """
    handler = FIX_REGISTRY.get(check)
    if handler is None:
        action_logger.log_action("FixDispatch", f"No handler for check: {check}", outcome="FAIL")
        return False
    action_logger.log_fix_dispatch(check)
    result = handler(specs)
    action_logger.log_fix_result(check, result)
    return result
