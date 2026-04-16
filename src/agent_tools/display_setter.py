import ctypes

from src.utils.display_utils import DEVMODE, ENUM_CURRENT_SETTINGS, enum_raw_modes

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


# ── Core: mode helpers ────────────────────────────────────────────────────────

def _get_current_mode(device_name: str) -> DEVMODE | None:
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ok = ctypes.windll.user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
    return dm if ok else None


def get_current_display_mode(device_name: str):
    """Public wrapper around _get_current_mode() for use by revert.py."""
    return _get_current_mode(device_name)


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

    all_modes = enum_raw_modes(device_name)

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
