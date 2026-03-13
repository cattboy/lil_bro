import wmi
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error, print_info

def check_rebar() -> dict:
    """
    Checks if Resizable BAR (Large Memory Range) is enabled
    by scanning Win32_DeviceMemoryAddress for ranges > 256MB.
    """
    print_step("Scanning Resizable BAR (ReBAR) Status")
    
    try:
        c = wmi.WMI()
        # Look for any memory range mapped to a device that is > 256 MB
        rebar_enabled = False
        max_size_mb = 0
        
        for mem in c.Win32_DeviceMemoryAddress():
            try:
                # WMI returns these as strings
                start = int(mem.StartingAddress)
                end = int(mem.EndingAddress)
                size_mb = (end - start + 1) / (1024 * 1024)
                
                if size_mb > max_size_mb:
                    max_size_mb = size_mb
                    
                if size_mb > 256.0:
                    rebar_enabled = True
                    break
            except (ValueError, TypeError, AttributeError):
                continue
                
        print_step_done(True)
        
        result = {
            "rebar_enabled": rebar_enabled,
            "max_range_mb": max_size_mb,
            "status": "OK"
        }
        
        if rebar_enabled:
            result["message"] = f"Resizable BAR is ENABLED (Large Memory Range detected: {max_size_mb:.0f} MB)."
            print_success(result["message"])
        else:
            result["status"] = "WARNING"
            result["message"] = f"Resizable BAR appears to be DISABLED. No device memory range > 256 MB found. Enable 'Above 4G Decoding' and 'Re-Size BAR Support' in your motherboard BIOS for better gaming performance."
            print_warning(result["message"])
            
        return result
        
    except Exception as e:
        print_step_done(False)
        print_error(f"Error checking Resizable BAR: {e}")
        return {"rebar_enabled": False, "max_range_mb": 0, "status": "ERROR", "message": str(e)}
