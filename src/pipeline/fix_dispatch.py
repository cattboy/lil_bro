"""
Fix dispatch registry -- maps check names to executable fix functions.

Each fix handler has the signature: (specs: dict) -> bool
To add a new auto-fixable check, add one handler function and one dict entry.
"""

from collections.abc import Callable

from src.utils.action_logger import action_logger
from src.utils.formatting import print_success, print_error


def _fix_display(specs: dict) -> bool:
    """Sets monitor to highest available refresh rate."""
    from src.collectors.sub.monitor_dumper import get_all_displays
    from src.agent_tools.display_setter import find_best_mode, apply_display_mode

    try:
        devices = get_all_displays()
        device = devices[0] if devices else "\\\\.\\DISPLAY1"
        mode = find_best_mode(device, target_hz=None, require_same_resolution=True)
        if mode is None:
            print_error("[display] No suitable mode found -- nothing changed.")
            return False
        ok, msg = apply_display_mode(device, mode, persist=True, dry_run=True)
        if not ok:
            print_error(f"[display] Validation failed: {msg}")
            return False
        ok, msg = apply_display_mode(device, mode, persist=True, dry_run=False)
        if ok:
            print_success(
                f"[display] Refresh rate set to {mode.dmDisplayFrequency}Hz "
                f"({mode.dmPelsWidth}x{mode.dmPelsHeight}). {msg}"
            )
        else:
            print_error(f"[display] Apply failed: {msg}")
        return ok
    except Exception as e:
        print_error(f"[display] Error: {e}")
        return False


def _fix_power_plan(specs: dict) -> bool:
    """Switches to a high-performance power plan."""
    from src.agent_tools.power_plan import (
        list_available_plans, set_active_plan,
        create_high_performance_plan, _PERF_GUIDS,
    )

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
        print_success(f"[power_plan] Switched to '{name}'.")
        return True
    except Exception as e:
        print_error(f"[power_plan] Failed: {e}")
        return False


def _fix_temp_folders(specs: dict) -> bool:
    """Cleans temporary file directories."""
    from src.agent_tools.temp_audit import clean_temp_folders

    details = specs.get("TempFolders", {}).get("details", {})
    try:
        clean_temp_folders(details)
        return True
    except Exception as e:
        print_error(f"[temp_folders] Cleanup failed: {e}")
        return False


def _fix_game_mode(specs: dict) -> bool:
    """Enables Windows Game Mode via registry."""
    from src.agent_tools.game_mode import set_game_mode

    try:
        set_game_mode(enabled=True)
        print_success("[game_mode] Game Mode enabled.")
        return True
    except Exception as e:
        print_error(f"[game_mode] Failed: {e}")
        return False


def _fix_nvidia_profile(specs: dict) -> bool:
    """Applies optimized NVIDIA driver profile via NPI."""
    from src.agent_tools.nvidia_profile_setter import fix_nvidia_profile

    try:
        fix_nvidia_profile(specs)
        print_success(
            "[nvidia_profile] NVIDIA driver profile optimized "
            "(G-Sync, VSync, FPS cap, DLSS, power management)."
        )
        return True
    except FileNotFoundError as e:
        print_error(f"[nvidia_profile] {e}")
        return False
    except Exception as e:
        print_error(f"[nvidia_profile] Failed: {e}")
        return False


# ---- Dispatch Registry ----
# Key: check name (matches proposal["finding"])
# Value: callable with signature (specs: dict) -> bool
FIX_REGISTRY: dict[str, Callable[[dict], bool]] = {
    "display": _fix_display,
    "power_plan": _fix_power_plan,
    "temp_folders": _fix_temp_folders,
    "game_mode": _fix_game_mode,
    "nvidia_profile": _fix_nvidia_profile,
}


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
