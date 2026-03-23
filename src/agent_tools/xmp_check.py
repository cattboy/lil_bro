try:
    import wmi
except ImportError:
    wmi = None
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error, print_info

def analyze_xmp(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected RAM data from specs dict.
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    ram_modules = specs.get("WMI", {}).get("RAM", [])
    if not ram_modules:
        return {
            "check": "xmp",
            "status": "ERROR",
            "current": 0,
            "message": "No RAM data in specs.",
            "can_auto_fix": False,
        }

    module = ram_modules[0]
    configured_mhz = int(module.get("Configured_MHz", 0) or 0)
    base_mhz = int(module.get("Speed_MHz", 0) or 0)
    active = configured_mhz if configured_mhz > 0 else base_mhz

    xmp_on = (
        (configured_mhz > 0 and base_mhz > 0 and configured_mhz > base_mhz) or
        (2666 < active < 4000) or  # DDR4 XMP territory
        (active >= 5200)           # DDR5 EXPO/XMP territory
    )

    if not xmp_on:
        return {
            "check": "xmp",
            "status": "WARNING",
            "current": active,
            "message": f"RAM running at {active}MHz — looks like base JEDEC speed. Enable XMP/EXPO in BIOS.",
            "can_auto_fix": False,
        }
    return {
        "check": "xmp",
        "status": "OK",
        "current": active,
        "message": f"RAM running at XMP/EXPO speeds ({active}MHz).",
        "can_auto_fix": False,
    }

def get_memory_speeds() -> tuple[int, int]:
    """
    Queries WMI to get the configured clock speed vs the base speed of RAM.
    Returns:
        (configured_speed, base_speed) in MHz.
        Returns (0, 0) if it cannot determine safely.
    """
    if wmi is None:
        raise ScannerError("WMI module not available.")
    try:
        c = wmi.WMI()
        modules = c.Win32_PhysicalMemory()
        
        if not modules:
            raise ScannerError("No physical memory modules detected by WMI.")
            
        # We'll just look at the first module for the baseline
        # (Usually if one is XMP, they all are, or system runs at lowest common denominator)
        module = modules[0]
        
        configured_speed = 0
        base_speed = 0
        
        if hasattr(module, 'ConfiguredClockSpeed') and module.ConfiguredClockSpeed:
            configured_speed = int(module.ConfiguredClockSpeed)
            
        if hasattr(module, 'Speed') and module.Speed:
            base_speed = int(module.Speed)
            
        return configured_speed, base_speed
        
    except Exception as e:
        raise ScannerError(f"Error querying WMI for memory speed: {e}")

def check_xmp_status() -> dict:
    """
    Runs the XMP/EXPO memory speed check.
    """
    print_step("Scanning RAM Speed (XMP/EXPO)")
    
    try:
        configured_speed, base_speed = get_memory_speeds()
        print_step_done(True)
        
        result = {
            "configured_mhz": configured_speed,
            "base_mhz": base_speed,
            "xmp_likely": False,
            "status": "OK"
        }
        
        if configured_speed == 0 and base_speed == 0:
             result["status"] = "ERROR"
             result["message"] = "Could not read memory speeds from WMI."
             print_error(result["message"])
             return result
             
        # Use whatever speed we have if one is missing but the other exists
        active_speed = configured_speed if configured_speed > 0 else base_speed
        
        # Typically DDR4 base is 2133-2666. DDR5 base is 4400-4800.
        # If ConfiguredClockSpeed > Speed, XMP is definitely on.
        # If we only have one metric to go by, we use a heuristic based on common high speeds.
        
        xmp_is_on = False
        
        if configured_speed > 0 and base_speed > 0 and configured_speed > base_speed:
            xmp_is_on = True
        elif active_speed > 2666 and active_speed < 4000:
            # DDR4 likely XMP
            xmp_is_on = True
        elif active_speed >= 5200:
            # DDR5 likely EXPO/XMP
            xmp_is_on = True
            
        result["xmp_likely"] = xmp_is_on
        
        if not xmp_is_on:
            result["status"] = "WARNING"
            result["message"] = f"Memory is running at {active_speed} MHz. This looks like base JEDEC speeds. Check your BIOS to ensure XMP or EXPO is enabled to get full performance."
            print_warning(result["message"])
        else:
            result["message"] = f"Memory is running at XMP/EXPO speeds ({active_speed} MHz)."
            print_success(result["message"])
            
        return result
        
    except ScannerError as e:
        print_step_done(False)
        print_error(str(e))
        return {"configured_mhz": 0, "base_mhz": 0, "xmp_likely": False, "status": "ERROR", "message": str(e)}
