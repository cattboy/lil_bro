try:
    import wmi
except ImportError:
    wmi = None
import subprocess
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error, print_info

def analyze_rebar(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected NVIDIA data from specs dict.
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    nvidia = specs.get("NVIDIA", "")

    if isinstance(nvidia, list) and nvidia:
        gpu = nvidia[0]
        rebar_on = gpu.get("ReBAR", False)          # bool from nvidia_smi_dumper
        bar1_mib = gpu.get("BAR1 Used (MiB)", 0)   # int, key includes parentheses
        name = gpu.get("GPU", "Unknown GPU")

        if rebar_on:
            return {
                "check": "rebar",
                "status": "OK",
                "current": True,
                "message": f"Resizable BAR is ENABLED ({name}, BAR1: {bar1_mib} MiB).",
                "can_auto_fix": False,
            }
        return {
            "check": "rebar",
            "status": "WARNING",
            "current": False,
            "message": f"Resizable BAR is DISABLED ({name}). Enable 'Above 4G Decoding' in BIOS.",
            "can_auto_fix": False,
        }

    return {
        "check": "rebar",
        "status": "UNKNOWN",
        "current": None,
        "message": "Could not determine ReBAR status — NVIDIA GPU not detected or nvidia-smi unavailable.",
        "can_auto_fix": False,
    }

def check_nvidia_rebar() -> tuple[bool | None, str]:
    """
    Checks ReBAR status using nvidia-smi.
    Returns (True/False, message) or (None, error_message) if not applicable.
    """
    try:
        result = subprocess.run([
            "nvidia-smi",
            "--query-gpu=name,memory.total,bar1.memory.total,bar1.memory.used",
            "--format=csv,noheader,nounits"
        ], capture_output=True, text=True, check=True)
        
        # Parse first GPU
        lines = result.stdout.strip().splitlines()
        if not lines:
            return None, "No output from nvidia-smi."
            
        name, vram, bar1_total, bar1_used = [x.strip() for x in lines[0].split(",")]
        
        # If BAR1 is > 256 MiB (often matches total VRAM or is very large)
        if int(bar1_total) > 256:
            return True, f"Resizable BAR is ENABLED ({name}, BAR1: {bar1_total} MiB)."
        else:
            return False, f"Resizable BAR is DISABLED ({name}, BAR1: {bar1_total} MiB)."
            
    except FileNotFoundError:
        return None, "nvidia-smi not found."
    except subprocess.CalledProcessError as e:
        return None, f"nvidia-smi failed: {e.stderr}"
    except Exception as e:
        return None, f"nvidia-smi error: {str(e)}"

def check_wmi_rebar() -> tuple[bool, float, str]:
    """
    Fallback method using WMI Win32_DeviceMemoryAddress to find large memory ranges.
    Returns (is_enabled, max_size_mb, message)
    """
    if wmi is None:
        raise ScannerError("WMI module not available.")
    rebar_enabled = False
    max_size_mb = 0.0

    try:
        c = wmi.WMI()
        for mem in c.Win32_DeviceMemoryAddress():
            try:
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
                
        if rebar_enabled:
            return True, max_size_mb, f"Resizable BAR is ENABLED (Large Memory Range detected: {max_size_mb:.0f} MB)."
        else:
            return False, max_size_mb, "Resizable BAR appears to be DISABLED. No device memory range > 256 MB found."
            
    except Exception as e:
        raise ScannerError(f"WMI error checking Resizable BAR: {e}")

def check_rebar() -> dict:
    """
    Checks if Resizable BAR is enabled using multiple heuristic methods.
    """
    print_step("Scanning Resizable BAR (ReBAR) Status")
    
    # 1. Try NVIDIA SMI (Most precise for NVIDIA)
    nv_status, nv_msg = check_nvidia_rebar()
    if nv_status is not None:
        print_step_done(True)
        
        result = {
            "rebar_enabled": nv_status,
            "max_range_mb": 0.0,
            "status": "OK" if nv_status else "WARNING",
            "message": nv_msg
        }
        
        if nv_status:
           print_success(result["message"])
        else:
           result["message"] = nv_msg + " Enable 'Above 4G Decoding' and 'Re-Size BAR Support' in your motherboard BIOS."
           print_warning(result["message"])
           
        return result
        
    # 2. Try WMI Device Memory Address fallback
    try:
        wmi_status, wmi_max_mb, wmi_msg = check_wmi_rebar()
        print_step_done(True)
        
        result = {
            "rebar_enabled": wmi_status,
            "max_range_mb": wmi_max_mb,
            "status": "OK" if wmi_status else "WARNING",
            "message": wmi_msg
        }
        
        if wmi_status:
            print_success(result["message"])
        else:
            result["message"] = wmi_msg + " Enable 'Above 4G Decoding' and 'Re-Size BAR Support' in your motherboard BIOS."
            print_warning(result["message"])
            
        return result
        
    except ScannerError as e:
        print_step_done(False)
        print_error(str(e))
        return {
            "rebar_enabled": False,
            "max_range_mb": 0.0,
            "status": "ERROR",
            "message": str(e)
        }
