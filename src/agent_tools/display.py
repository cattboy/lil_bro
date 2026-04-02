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
