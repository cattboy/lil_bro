try:
    import winreg
except ImportError:
    winreg = None  # type: ignore  # not available on non-Windows

from ..utils.errors import ScannerError
from ..utils.action_logger import action_logger

def analyze_game_mode(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected Game Mode state from specs dict.
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    game_mode = specs.get("GameMode", {})
    enabled = game_mode.get("enabled", True)

    if not enabled:
        return {
            "check": "game_mode",
            "status": "WARNING",
            "current": False,
            "expected": True,
            "message": "Windows Game Mode is DISABLED — lil_bro can flip this on for you.",
            "can_auto_fix": True,
        }
    return {
        "check": "game_mode",
        "status": "OK",
        "current": True,
        "expected": True,
        "message": "Windows Game Mode is ENABLED.",
        "can_auto_fix": False,
    }

def set_game_mode(enabled: bool) -> bool:
    """
    Sets Windows Game Mode on/off by writing AutoGameModeEnabled.

    Args:
        enabled: True to enable Game Mode, False to disable.

    Returns:
        True if the write succeeded.

    Raises:
        ScannerError: If the registry write fails.
    """
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\GameBar",
            0,
            winreg.KEY_SET_VALUE,
        ) as key:
            winreg.SetValueEx(key, "AutoGameModeEnabled", 0, winreg.REG_DWORD, 1 if enabled else 0)
        action_logger.log_action(
            "Game Mode",
            f"Set AutoGameModeEnabled = {1 if enabled else 0}",
            r"HKCU\SOFTWARE\Microsoft\GameBar",
        )
        return True
    except Exception as e:
        raise ScannerError(f"Failed to set Game Mode: {e}")


def get_game_mode_status() -> bool:
    """
    Checks the registry for AutoGameModeEnabled.
    Returns:
        True if enabled (or default missing key on modern Win10+)
        False if explicitly disabled
    """
    try:
        # Open HKEY_CURRENT_USER\SOFTWARE\Microsoft\GameBar
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\GameBar") as key:
            try:
                # Value is usually a DWORD: 1 = enabled, 0 = disabled
                value, regtype = winreg.QueryValueEx(key, "AutoGameModeEnabled")
                return value != 0
            except FileNotFoundError:
                # Key doesn't exist. On modern Windows 10/11, it is enabled by default.
                return True
    except FileNotFoundError:
        # GameBar key doesn't exist, assume default Game Mode behavior (enabled)
        return True
    except Exception as e:
        raise ScannerError(f"Error reading Game Mode registry key: {e}")
