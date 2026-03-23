import ctypes
from ctypes import wintypes
from ..utils.formatting import prompt_approval

### exact match (find a mode that exactly matches target Hz) and best available (find the highest Hz the monitor supports):
### Key design decisions to call out
# Always validate before applying. The CDS_TEST dry-run pass catches cases where EnumDisplaySettings listed a mode but the driver rejects it at apply time (this happens with some cable/adapter combinations — the EDID lied about what the signal path can carry).
# dmFields must be explicit. A very common bug — if you don't set dmFields to declare which struct members are intentional, Windows ignores them or uses garbage values from uninitialized memory.
# persist=True vs False. Without CDS_UPDATEREGISTRY the change reverts on next login. For a "fix misconfigured monitors" tool you almost certainly want persist=True, but exposing both is useful for testing.
# Resolution is preserved by default. require_same_resolution=True in find_best_mode ensures you only touch Hz, not the user's chosen resolution. Accidentally dropping from 2560x1440 to 1920x1080 to hit a higher Hz would be a bad surprise.
# DISP_CHANGE_RESTART is still success. Return code 1 means the mode is valid but needs a reboot — treat it as success and log it, don't treat it as a failure.
# ── DEVMODE (reuse from your existing code) ────────────────────────────────────

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",        ctypes.c_wchar * 32),
        ("dmSpecVersion",       wintypes.WORD),
        ("dmDriverVersion",     wintypes.WORD),
        ("dmSize",              wintypes.WORD),
        ("dmDriverExtra",       wintypes.WORD),
        ("dmFields",            wintypes.DWORD),
        ("dmPositionX",         ctypes.c_long),
        ("dmPositionY",         ctypes.c_long),
        ("dmDisplayOrientation",wintypes.DWORD),
        ("dmDisplayFixedOutput",wintypes.DWORD),
        ("dmColor",             ctypes.c_short),
        ("dmDuplex",            ctypes.c_short),
        ("dmYResolution",       ctypes.c_short),
        ("dmTTOption",          ctypes.c_short),
        ("dmCollate",           ctypes.c_short),
        ("dmFormName",          ctypes.c_wchar * 32),
        ("dmLogPixels",         wintypes.WORD),
        ("dmBitsPerPel",        wintypes.DWORD),
        ("dmPelsWidth",         wintypes.DWORD),
        ("dmPelsHeight",        wintypes.DWORD),
        ("dmDisplayFlags",      wintypes.DWORD),
        ("dmDisplayFrequency",  wintypes.DWORD),
        ("dmICMMethod",         wintypes.DWORD),
        ("dmICMIntent",         wintypes.DWORD),
        ("dmMediaType",         wintypes.DWORD),
        ("dmDitherType",        wintypes.DWORD),
        ("dmReserved1",         wintypes.DWORD),
        ("dmReserved2",         wintypes.DWORD),
        ("dmPanningWidth",      wintypes.DWORD),
        ("dmPanningHeight",     wintypes.DWORD),
    ]

# ── ChangeDisplaySettingsEx flags ──────────────────────────────────────────────

CDS_TEST           = 0x00000002  # Dry-run: validate only, don't apply
CDS_UPDATEREGISTRY = 0x00000001  # Persist across reboots
CDS_NORESET        = 0x10000000  # Stage change without applying (batch use)

# Return codes from ChangeDisplaySettingsEx
DISP_CHANGE_SUCCESSFUL =  0
DISP_CHANGE_RESTART    =  1   # Need reboot (rare on modern systems)
DISP_CHANGE_FAILED     = -1
DISP_CHANGE_BADMODE    = -2   # Mode not supported - your validation caught a lie
DISP_CHANGE_BADPARAM   = -5

DISP_CHANGE_MESSAGES = {
    0:  "Success",
    1:  "Success (reboot required to fully apply)",
   -1:  "Failed (driver rejected the mode)",
   -2:  "Bad mode (not supported for this display)",
   -3:  "Failed (display write failed)",
   -4:  "Failed (requires different display mode)",
   -5:  "Bad parameters passed",
   -6:  "Failed (video driver error)",
   -8:  "Failed (unable to write settings)",
}

# dmFields flags — tells Windows which DEVMODE fields are actually populated
DM_PELSWIDTH       = 0x00080000
DM_PELSHEIGHT      = 0x00100000
DM_DISPLAYFREQUENCY= 0x00400000
DM_BITSPERPEL      = 0x00040000


# ── Core: enumerate modes (same as before, kept here for self-containment) ─────

ENUM_CURRENT_SETTINGS = -1

def _get_current_mode(device_name: str) -> DEVMODE | None:
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ok = ctypes.windll.user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
    return dm if ok else None

def _enum_all_modes(device_name: str) -> list[DEVMODE]:
    modes = []
    i = 0
    while True:
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        if not ctypes.windll.user32.EnumDisplaySettingsW(device_name, i, ctypes.byref(dm)):
            break
        modes.append(dm)
        i += 1
    return modes


# ── Mode selection strategies ──────────────────────────────────────────────────

def find_best_mode(
    device_name: str,
    target_hz: int | None = None,
    require_same_resolution: bool = True,
) -> DEVMODE | None:
    """
    Finds the best DEVMODE to apply.
    
    - If target_hz is given: find a mode matching that exact Hz at the current resolution.
    - If target_hz is None: find the highest Hz mode at the current resolution.
    - If require_same_resolution=False: allow resolution changes too (picks highest
      Hz regardless of resolution — use carefully).

    Returns None if no suitable mode found.
    """
    current = _get_current_mode(device_name)
    if current is None:
        return None

    all_modes = _enum_all_modes(device_name)

    # Filter to same resolution unless caller explicitly allows changes
    if require_same_resolution:
        candidates = [
            m for m in all_modes
            if m.dmPelsWidth == current.dmPelsWidth
            and m.dmPelsHeight == current.dmPelsHeight
        ]
    else:
        candidates = all_modes

    if not candidates:
        return None

    if target_hz is not None:
        # Exact match on Hz
        matches = [m for m in candidates if m.dmDisplayFrequency == target_hz]
        return matches[0] if matches else None
    else:
        # Best available: highest Hz, use highest resolution as tiebreaker
        return max(candidates, key=lambda m: (m.dmDisplayFrequency, m.dmPelsWidth, m.dmPelsHeight))


# ── Core apply function ────────────────────────────────────────────────────────

def apply_display_mode(
    device_name: str,
    mode: DEVMODE,
    persist: bool = True,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """
    Applies a DEVMODE to the specified display.

    Args:
        device_name:  e.g. '\\\\.\\DISPLAY1'
        mode:         A DEVMODE returned from find_best_mode()
        persist:      If True, writes to registry (survives reboot).
                      If False, applies for this session only.
        dry_run:      If True, only validates — does not actually change anything.

    Returns:
        (success: bool, message: str)
    """
    # Always explicitly declare which fields we're setting
    mode.dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_DISPLAYFREQUENCY | DM_BITSPERPEL
    mode.dmSize   = ctypes.sizeof(DEVMODE)

    flags = CDS_TEST if dry_run else (CDS_UPDATEREGISTRY if persist else 0)

    result = ctypes.windll.user32.ChangeDisplaySettingsExW(
        device_name,
        ctypes.byref(mode),
        None,   # hWnd — always None for fullscreen/desktop mode changes
        flags,
        None    # lParam — reserved
    )

    message = DISP_CHANGE_MESSAGES.get(result, f"Unknown return code: {result}")
    success = result in (DISP_CHANGE_SUCCESSFUL, DISP_CHANGE_RESTART)
    return success, message


# ── High-level convenience functions ──────────────────────────────────────────

def set_max_refresh_rate(
    device_name: str,
    persist: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    One-shot: find and apply the maximum refresh rate for a display,
    keeping the current resolution intact.
    """
    current = _get_current_mode(device_name)
    if current is None:
        return {"success": False, "error": "Could not read current display mode"}

    current_hz = current.dmDisplayFrequency
    best_mode  = find_best_mode(device_name, target_hz=None, require_same_resolution=True)

    if best_mode is None:
        return {"success": False, "error": "No candidate modes found"}

    if best_mode.dmDisplayFrequency <= current_hz:
        return {
            "success": True,
            "already_optimal": True,
            "current_hz": current_hz,
            "message": "Already at or above the best available refresh rate"
        }

    # Validate first (dry run), then apply if valid
    ok, msg = apply_display_mode(device_name, best_mode, persist=persist, dry_run=True)
    if not ok:
        return {"success": False, "error": f"Validation failed: {msg}"}

    if dry_run:
        return {
            "success": True,
            "dry_run": True,
            "would_change_from_hz": current_hz,
            "would_change_to_hz": best_mode.dmDisplayFrequency,
            "resolution": f"{best_mode.dmPelsWidth}x{best_mode.dmPelsHeight}",
        }

    if not prompt_approval(f"Set refresh rate to {best_mode.dmDisplayFrequency}Hz on {device_name}?"):
        return {"success": False, "cancelled": True, "message": "User declined refresh rate change."}

    ok, msg = apply_display_mode(device_name, best_mode, persist=persist, dry_run=False)
    return {
        "success": ok,
        "changed_from_hz": current_hz,
        "changed_to_hz":   best_mode.dmDisplayFrequency if ok else current_hz,
        "resolution":      f"{best_mode.dmPelsWidth}x{best_mode.dmPelsHeight}",
        "persisted":       persist,
        "message":         msg,
    }


def set_refresh_rate(
    device_name: str,
    target_hz: int,
    persist: bool = True,
    dry_run: bool = False,
) -> dict:
    """
    Set a specific refresh rate. Useful if you want 120Hz not 165Hz,
    e.g. for OLED burn-in reasons or compatibility.
    """
    mode = find_best_mode(device_name, target_hz=target_hz, require_same_resolution=True)
    if mode is None:
        return {
            "success": False,
            "error": f"{target_hz}Hz not found in supported modes for {device_name}"
        }

    ok, msg = apply_display_mode(device_name, mode, persist=persist, dry_run=True)
    if not ok:
        return {"success": False, "error": f"Validation failed: {msg}"}

    if dry_run:
        return {"success": True, "dry_run": True, "would_apply_hz": target_hz}

    if not prompt_approval(f"Set refresh rate to {target_hz}Hz on {device_name}?"):
        return {"success": False, "cancelled": True, "message": "User declined refresh rate change."}

    ok, msg = apply_display_mode(device_name, mode, persist=persist, dry_run=False)
    return {"success": ok, "applied_hz": target_hz if ok else None, "message": msg}


# ── Scan all monitors and fix any running below max ───────────────────────────

def fix_all_monitors(persist: bool = True, dry_run: bool = False) -> list[dict]:
    """
    Iterates all active displays and upgrades any running below
    their maximum supported refresh rate.
    """
    from ..collectors.sub.monitor_dumper import get_all_displays
    results = []
    for device in get_all_displays():
        result = set_max_refresh_rate(device, persist=persist, dry_run=dry_run)
        result["device"] = device
        results.append(result)
    return results


if __name__ == "__main__":
    import json
    # Dry run first to see what would change
    print("=== Dry Run ===")
    print(json.dumps(fix_all_monitors(dry_run=True), indent=2))

    # Uncomment to actually apply:
    # print("=== Applying ===")
    # print(json.dumps(fix_all_monitors(dry_run=False), indent=2))