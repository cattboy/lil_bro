import ctypes
import time
from ctypes import wintypes
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_info

def _fallback_measure_rate(duration_seconds: int) -> float:
    """
    A simpler Python-friendly heuristic for high polling rates:
    Rapidly poll GetCursorPos in a tight loop and count unique (x,y) or state changes per second.
    """
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
        
    start_time = time.time()
    last_pos = POINT(0, 0)
    samples = 0

    while (time.time() - start_time) < duration_seconds:
        current_pos = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(current_pos))
        
        if (current_pos.x != last_pos.x) or (current_pos.y != last_pos.y):
            samples += 1
            last_pos = current_pos
            
    # Calculate average Hz. Note: polling GetCursorPos in Python might cap out around ~500-1000Hz 
    # depending on the GIL and system timer resolution, so it serves as a rough estimate.
    hz = samples / duration_seconds
    return round(hz)

def check_polling_rate() -> dict:
    """
    Runs the mouse polling rate check and returns the diagnostic.
    """
    print_step("Scanning Mouse Polling Rate")
    print_step_done(True) # Just to close the line

    try:
        hz = _fallback_measure_rate(2)
    except Exception as e:
        return {"current_hz": 0, "status": "ERROR", "message": str(e)}
    
    result = {
        "current_hz": hz,
        "status": "OK"
    }
    
    if hz < 500:
        result["status"] = "WARNING"
        result["message"] = f"Mouse polling rate measured at roughly {hz}Hz. This is low for gaming (adds input lag). Check your mouse software settings and ensure it is set to 1000Hz or higher."
        print_warning(result["message"])
    elif hz < 1000:
        result["status"] = "OK"
        result["message"] = f"Mouse polling rate measured at roughly {hz}Hz. This is acceptable, but 1000Hz is preferred for competitive esports."
        print_success(result["message"])
    else:
        result["status"] = "OK"
        result["message"] = f"Mouse polling rate measured at roughly {hz}Hz. Fast and optimal!"
        print_success(result["message"])
        
    return result
