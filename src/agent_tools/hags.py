"""Hardware-Accelerated GPU Scheduling (HAGS) detection + toggle.

À-la-carte counterpart to the Game Mode fix: a single revertible registry
toggle. HAGS is controlled by the DWORD ``HwSchMode`` under
``HKLM\\SYSTEM\\CurrentControlSet\\Control\\GraphicsDrivers`` (2 = enabled,
1 = disabled). Mirrors game_mode.py's read/write/analyze shape, with two
differences: the key lives in HKLM (writes need the elevated process the
bootstrapper already enforces), and the change only takes effect after a
reboot.

The ``HwSchMode`` value is present only on WDDM 2.7+ GPUs/drivers that expose
HAGS; its absence means the feature is unsupported, surfaced via the
``supported`` flag so the analyzer / Dashboard card hide rather than offer a
no-op fix.
"""

try:
    import winreg
except ImportError:
    winreg = None  # type: ignore  # not available on non-Windows

from ..utils.errors import ScannerError
from ..utils.action_logger import action_logger

_HAGS_KEY = r"SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
_HAGS_VALUE = "HwSchMode"


def analyze_hags(specs: dict) -> dict:
    """Pure analyzer. Reads pre-collected HAGS state from specs dict.

    Returns a standardized finding dict -- no system calls, no terminal output.
    SKIPPED when HAGS is unsupported (or collection failed): the Dashboard card
    hides and the pipeline never offers a fix that would be a silent no-op.
    """
    hags = specs.get("HAGS", {})
    if not isinstance(hags, dict) or "error" in hags or not hags.get("supported", False):
        return {
            "check": "hags",
            "status": "SKIPPED",
            "message": "Hardware-Accelerated GPU Scheduling is not supported on this GPU/driver.",
            "can_auto_fix": False,
        }

    enabled = hags.get("enabled", False)
    if not enabled:
        return {
            "check": "hags",
            "status": "WARNING",
            "current": False,
            "expected": True,
            "message": "Hardware-Accelerated GPU Scheduling is DISABLED — lil_bro can flip this on for you.",
            "can_auto_fix": True,
        }
    return {
        "check": "hags",
        "status": "OK",
        "current": True,
        "expected": True,
        "message": "Hardware-Accelerated GPU Scheduling is ENABLED.",
        "can_auto_fix": False,
    }


def set_hags(enabled: bool) -> bool:
    """Enable/disable HAGS by writing HwSchMode to HKEY_LOCAL_MACHINE.

    Args:
        enabled: True to enable HAGS (HwSchMode=2), False to disable (=1).

    Returns:
        True if the write succeeded.

    Raises:
        ScannerError: If the registry write fails (e.g. not elevated).
    """
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_LOCAL_MACHINE,
            _HAGS_KEY,
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, _HAGS_VALUE, 0, winreg.REG_DWORD, 2 if enabled else 1)
        action_logger.log_action(
            "HAGS",
            f"Set HwSchMode = {2 if enabled else 1}",
            r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers",
        )
        return True
    except Exception as e:
        raise ScannerError(f"Failed to set HAGS: {e}")


def get_hags_status() -> dict:
    """Read HwSchMode from HKLM\\...\\GraphicsDrivers.

    Returns a dict ``{"enabled": bool, "supported": bool}``:
        * value == 2          -> enabled, supported
        * value present, != 2 -> disabled, supported
        * value absent        -> disabled, NOT supported (feature not exposed)
    """
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _HAGS_KEY) as key:
            try:
                value, _ = winreg.QueryValueEx(key, _HAGS_VALUE)
                return {"enabled": value == 2, "supported": True}
            except FileNotFoundError:
                # Value absent: HAGS not exposed by this GPU/driver (pre-WDDM 2.7).
                return {"enabled": False, "supported": False}
    except FileNotFoundError:
        # GraphicsDrivers key missing entirely -- treat as unsupported.
        return {"enabled": False, "supported": False}
    except Exception as e:
        raise ScannerError(f"Error reading HAGS registry key: {e}")
