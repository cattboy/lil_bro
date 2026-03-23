try:
    import wmi
except ImportError:
    wmi = None
import winreg
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error

def analyze_display(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected display data from specs dict.
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    displays = specs.get("DisplayCapabilities", [])
    if not displays:
        return {
            "check": "display",
            "status": "ERROR",
            "current": 0,
            "message": "No display capability data in specs.",
            "can_auto_fix": False,
        }

    primary = displays[0]
    current_hz = primary.get("current_refresh_hz", 0)
    max_hz = primary.get("max_refresh_hz", 0)
    edid_max = primary.get("edid_declared_max_hz") or 0
    best_max = max(max_hz, edid_max)

    if best_max > 0 and current_hz < best_max:
        return {
            "check": "display",
            "status": "WARNING",
            "current": current_hz,
            "expected": best_max,
            "message": f"Monitor running at {current_hz}Hz but supports up to {best_max}Hz.",
            "can_auto_fix": True,
        }
    return {
        "check": "display",
        "status": "OK",
        "current": current_hz,
        "expected": best_max or current_hz,
        "message": f"Monitor running at optimal {current_hz}Hz.",
        "can_auto_fix": False,
    }

def get_current_refresh_rate() -> int:
    """Queries WMI for the current monitor refresh rate."""
    if wmi is None:
        raise ScannerError("WMI module not available.")
    try:
        c = wmi.WMI()
        # Get the first active video controller
        # In a multi-monitor setup, this represents the primary display usually.
        # WMI Win32_VideoController can sometimes return a list of adapters, some virtual.
        # We look for one with a valid CurrentRefreshRate.
        controllers = c.Win32_VideoController()
        for controller in controllers:
            if hasattr(controller, 'CurrentRefreshRate') and controller.CurrentRefreshRate is not None:
                return int(controller.CurrentRefreshRate)
                
        raise ScannerError("Could not determine current refresh rate via WMI.")
    except Exception as e:
         raise ScannerError(f"Error querying WMI: {e}")

def get_native_refresh_rate() -> int:
    """
    Attempts to read max refresh rate from EDID in the registry.
    This is complex in Python. For the PoC, we will use a simplified heuristic 
    or target a specific known EDID parsing method if available.
    
    Since fully parsing EDID binaries is complex, we'll return a placeholder or 
    attempt a basic registry scan.
    """
    # NOTE: Fully parsing EDID bytes from the registry to extract detailed timings 
    # (like 240Hz) requires a complex byte parser.
    # For Week 1 PoC, we'll simulate this by returning a common high-end value 
    # if we can't parse it, or just rely on WMI MaxRefreshRate if available.
    
    try:
        c = wmi.WMI()
        controllers = c.Win32_VideoController()
        for controller in controllers:
            if hasattr(controller, 'MaxRefreshRate') and controller.MaxRefreshRate is not None:
                return int(controller.MaxRefreshRate)
        return 0 # Unknown
    except Exception:
        return 0 # Unknown

def check_refresh_rate() -> dict:
    """
    Runs the display refresh rate check.
    """
    print_step("Scanning display configuration")
    
    try:
        current_rr = get_current_refresh_rate()
        print_step_done(True)
        
        # In a real scenario, we'd parse EDID. For PoC, we flag if it's 60Hz 
        # (common default issue for high refresh rate monitors).
        
        result = {
            "current_hz": current_rr,
            "status": "OK"
        }
        
        if current_rr <= 60:
            result["status"] = "WARNING"
            result["message"] = f"Your monitor is currently running at {current_rr}Hz. If you have a high refresh rate gaming monitor (144Hz, 240Hz, etc.), please check your Windows Display Settings!"
            print_warning(result["message"])
        else:
            result["message"] = f"Monitor running at a healthy {current_rr}Hz."
            print_success(result["message"])
            
        return result
        
    except ScannerError as e:
        print_step_done(False)
        print_error(str(e))
        return {"current_hz": 0, "status": "ERROR", "message": str(e)}
