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
