import winreg
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error

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

def check_game_mode() -> dict:
    """
    Runs the Windows Game Mode check.
    """
    print_step("Scanning Windows Game Mode status")
    
    try:
        is_enabled = get_game_mode_status()
        print_step_done(True)
        
        result = {
            "enabled": is_enabled,
            "status": "OK"
        }
        
        if not is_enabled:
            result["status"] = "WARNING"
            result["message"] = "Windows Game Mode is DISABLED. It is recommended to enable this in Windows Settings (Settings > Gaming > Game Mode) for better performance and resource allocation during gaming."
            print_warning(result["message"])
        else:
            result["message"] = "Windows Game Mode is ENABLED."
            print_success(result["message"])
            
        return result
        
    except ScannerError as e:
        print_step_done(False)
        print_error(str(e))
        return {"enabled": False, "status": "ERROR", "message": str(e)}
