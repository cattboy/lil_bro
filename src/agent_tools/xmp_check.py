import wmi
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error, print_info

def get_memory_speeds() -> tuple[int, int]:
    """
    Queries WMI to get the configured clock speed vs the base speed of RAM.
    Returns:
        (configured_speed, base_speed) in MHz.
        Returns (0, 0) if it cannot determine safely.
    """
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
