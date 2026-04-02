try:
    import wmi
except ImportError:
    wmi = None


def _check_rebar_wmi(c) -> dict:
    """Uses Win32_DeviceMemoryAddress to detect ReBAR — works for AMD/Intel when nvidia-smi is unavailable."""
    for mem in c.Win32_DeviceMemoryAddress():
        try:
            size_mb = (int(mem.EndingAddress) - int(mem.StartingAddress) + 1) / (1024 * 1024)
            if size_mb > 256.0:
                return {"enabled": True, "max_range_mb": size_mb}
        except (ValueError, TypeError, AttributeError):
            continue
    return {"enabled": False, "max_range_mb": 0.0}


def get_wmi_specs() -> dict:
    if wmi is None:
        return {"error": "WMI module not installed or unsupported OS"}
    try:
        c = wmi.WMI()
        return {
            "OS": [{"Name": o.Caption, "Version": o.Version} for o in c.Win32_OperatingSystem()],
            "CPU": [{"Name": p.Name, "Cores": p.NumberOfCores, "Speed_MHz": p.MaxClockSpeed} for p in c.Win32_Processor()],
            "RAM": [{"Capacity_GB": round(int(r.Capacity)/1e9, 1), "Speed_MHz": r.Speed, "Configured_MHz": getattr(r, 'ConfiguredClockSpeed', 0)} for r in c.Win32_PhysicalMemory()],
            "Motherboard": [{"Make": m.Manufacturer, "Model": m.Product} for m in c.Win32_BaseBoard()],
            "BIOS": [{"Version": b.SMBIOSBIOSVersion} for b in c.Win32_BIOS()],
            "VideoController": [{"Name": v.Name, "VRAM_MB": int(getattr(v, 'AdapterRAM', 0) or 0) / (1024*1024), "RefreshRate": getattr(v, 'CurrentRefreshRate', 0)} for v in c.Win32_VideoController()],
            "DiskDrive": [{"Model": d.Model, "Size_GB": round(int(d.Size or 0)/1e9, 1)} for d in c.Win32_DiskDrive()],
            "ReBAR": _check_rebar_wmi(c),
        }
    except Exception as e:
        return {"error": f"WMI query failed: {e}"}