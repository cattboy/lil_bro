def analyze_rebar(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected hardware data from specs dict.
    NVIDIA path: specs["NVIDIA"][0]["ReBAR"] (set by nvidia_smi_dumper).
    AMD/Intel fallback: specs["WMI"]["ReBAR"] (set by wmi_dumper via Win32_DeviceMemoryAddress).
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    nvidia = specs.get("NVIDIA", "")

    if isinstance(nvidia, list) and nvidia:
        gpu = nvidia[0]
        rebar_on = gpu.get("ReBAR", False)
        bar1_mib = gpu.get("BAR1 Used (MiB)", 0)
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

    wmi_rebar = specs.get("WMI", {}).get("ReBAR")
    if isinstance(wmi_rebar, dict):
        enabled = wmi_rebar.get("enabled", False)
        max_mb = wmi_rebar.get("max_range_mb", 0.0)
        if enabled:
            return {
                "check": "rebar",
                "status": "OK",
                "current": True,
                "message": f"Resizable BAR is ENABLED (large memory range detected: {max_mb:.0f} MB).",
                "can_auto_fix": False,
            }
        return {
            "check": "rebar",
            "status": "WARNING",
            "current": False,
            "message": "Resizable BAR is DISABLED. Enable 'Above 4G Decoding' in BIOS.",
            "can_auto_fix": False,
        }

    return {
        "check": "rebar",
        "status": "UNKNOWN",
        "current": None,
        "message": "Could not determine ReBAR status — NVIDIA GPU not detected or nvidia-smi unavailable.",
        "can_auto_fix": False,
    }
