import ctypes
from ctypes import wintypes
import winreg

# EnumDisplaySettings Win32 API via ctypes ✅ Best approach
# This calls the Windows ChangeDisplaySettingsEx / 
# EnumDisplaySettings API which queries the driver's enumerated mode list — these come from the monitor's EDID a
# nd the GPU driver's supported mode table. It gives you every resolution + refresh rate combination the system 
# considers valid for that display. No extra tools needed, pure Python.
# 6. WMI Win32_DesktopMonitor + EDID from registry ✅ Good supplement
# The raw EDID blob lives at HKLM\SYSTEM\CurrentControlSet\Enum\DISPLAY\...\Device Parameters\EDID.
#  Parsing it gives you the monitor manufacturer's declared max, independent of driver enumeration.


# ── EnumDisplaySettings approach ──────────────────────────────────────────────

ENUM_CURRENT_SETTINGS  = -1
ENUM_REGISTRY_SETTINGS = -2

class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",       ctypes.c_wchar * 32),
        ("dmSpecVersion",      wintypes.WORD),
        ("dmDriverVersion",    wintypes.WORD),
        ("dmSize",             wintypes.WORD),
        ("dmDriverExtra",      wintypes.WORD),
        ("dmFields",           wintypes.DWORD),
        ("dmPositionX",        ctypes.c_long),   # part of POINTL union
        ("dmPositionY",        ctypes.c_long),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor",            ctypes.c_short),
        ("dmDuplex",           ctypes.c_short),
        ("dmYResolution",      ctypes.c_short),
        ("dmTTOption",         ctypes.c_short),
        ("dmCollate",          ctypes.c_short),
        ("dmFormName",         ctypes.c_wchar * 32),
        ("dmLogPixels",        wintypes.WORD),
        ("dmBitsPerPel",       wintypes.DWORD),
        ("dmPelsWidth",        wintypes.DWORD),
        ("dmPelsHeight",       wintypes.DWORD),
        ("dmDisplayFlags",     wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),  # ← refresh rate in Hz
        ("dmICMMethod",        wintypes.DWORD),
        ("dmICMIntent",        wintypes.DWORD),
        ("dmMediaType",        wintypes.DWORD),
        ("dmDitherType",       wintypes.DWORD),
        ("dmReserved1",        wintypes.DWORD),
        ("dmReserved2",        wintypes.DWORD),
        ("dmPanningWidth",     wintypes.DWORD),
        ("dmPanningHeight",    wintypes.DWORD),
    ]

def enum_display_modes(device_name: str | None = None) -> list[dict]:
    """
    Returns all supported display modes for a given device (e.g. '\\\\.\\DISPLAY1').
    If device_name is None, uses the primary display.
    Crucially this iterates ALL modes the driver exposes, not just the current one.
    """
    user32 = ctypes.windll.user32
    modes = []
    i = 0
    while True:
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        # iModeNum counts up until it returns 0 (no more modes)
        if not user32.EnumDisplaySettingsW(device_name, i, ctypes.byref(dm)):
            break
        modes.append({
            "width":        dm.dmPelsWidth,
            "height":       dm.dmPelsHeight,
            "refresh_hz":   dm.dmDisplayFrequency,
            "bit_depth":    dm.dmBitsPerPel,
        })
        i += 1
    return modes

def get_max_refresh_for_device(device_name: str | None = None) -> dict:
    """Returns the maximum refresh rate (and the resolution it's available at)."""
    modes = enum_display_modes(device_name)
    if not modes:
        return {"error": "No modes found"}
    best = max(modes, key=lambda m: (m["refresh_hz"], m["width"], m["height"]))
    return {
        "max_refresh_hz": best["refresh_hz"],
        "at_resolution":  f"{best['width']}x{best['height']}",
        "current_refresh_hz": get_current_refresh(device_name),
        "all_refresh_rates": sorted({m["refresh_hz"] for m in modes}, reverse=True),
    }

def get_current_refresh(device_name: str | None = None) -> int:
    """Returns only the currently active refresh rate."""
    dm = DEVMODE()
    dm.dmSize = ctypes.sizeof(DEVMODE)
    ctypes.windll.user32.EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(dm))
    return dm.dmDisplayFrequency


# ── Multi-monitor enumeration ──────────────────────────────────────────────────

def get_all_displays() -> list[str]:
    """Returns device names like ['\\\\.\\DISPLAY1', '\\\\.\\DISPLAY2', ...]"""
    from ctypes import wintypes
    
    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ("cb",           wintypes.DWORD),
            ("DeviceName",   ctypes.c_wchar * 32),
            ("DeviceString", ctypes.c_wchar * 128),
            ("StateFlags",   wintypes.DWORD),
            ("DeviceID",     ctypes.c_wchar * 128),
            ("DeviceKey",    ctypes.c_wchar * 128),
        ]

    DISPLAY_DEVICE_ACTIVE = 0x00000001
    user32 = ctypes.windll.user32
    devices = []
    i = 0
    while True:
        dd = DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        if dd.StateFlags & DISPLAY_DEVICE_ACTIVE:
            devices.append(dd.DeviceName)
        i += 1
    return devices


# ── EDID cross-check (optional but useful for validation) ─────────────────────

def get_edid_max_refresh_from_registry() -> list[dict]:
    """
    Reads raw EDID bytes from the Windows registry and extracts the
    monitor-declared max vertical refresh from the Monitor Range Limits
    descriptor (tag 0xFD). This is the hardware ground truth.
    """
    results = []
    base_key = r"SYSTEM\CurrentControlSet\Enum\DISPLAY"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_key) as display_key:
            monitor_idx = 0
            while True:
                try:
                    monitor_name = winreg.EnumKey(display_key, monitor_idx)
                    monitor_idx += 1
                    with winreg.OpenKey(display_key, monitor_name) as mon_key:
                        inst_idx = 0
                        while True:
                            try:
                                instance = winreg.EnumKey(mon_key, inst_idx)
                                inst_idx += 1
                                params_path = f"{base_key}\\{monitor_name}\\{instance}\\Device Parameters"
                                try:
                                    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, params_path) as params:
                                        edid_bytes, _ = winreg.QueryValueEx(params, "EDID")
                                        max_hz = _parse_edid_max_refresh(bytes(edid_bytes))
                                        if max_hz:
                                            results.append({
                                                "monitor": monitor_name,
                                                "edid_max_refresh_hz": max_hz
                                            })
                                except (FileNotFoundError, OSError):
                                    pass
                            except OSError:
                                break
                except OSError:
                    break
    except Exception as e:
        return [{"error": str(e)}]
    return results

def _parse_edid_max_refresh(edid: bytes) -> int | None:
    """
    Finds the Monitor Range Limits descriptor (tag 0xFD) in the 128-byte
    base EDID block and returns max vertical refresh in Hz.
    EDID spec: descriptor blocks start at byte 54, each is 18 bytes.
    """
    if len(edid) < 128:
        return None
    for block_start in range(54, 109, 18):   # 4 descriptor blocks
        if edid[block_start] == 0 and edid[block_start+1] == 0 and edid[block_start+3] == 0xFD:
            # Byte offsets within descriptor:
            # +5 = min vertical rate, +6 = max vertical rate (Hz)
            max_v_hz = edid[block_start + 6]
            return max_v_hz
    return None  # descriptor not present (some cheap monitors omit it)


# ── Main entry point ───────────────────────────────────────────────────────────

def get_monitor_refresh_capabilities() -> list[dict]:
    displays = get_all_displays()
    results = []
    edid_data = {e["monitor"]: e.get("edid_max_refresh_hz") 
                 for e in get_edid_max_refresh_from_registry() 
                 if "monitor" in e}

    for device in displays:
        info = get_max_refresh_for_device(device)
        info["device"] = device
        # Attach EDID ground-truth if we can match it (best-effort name match)
        for mon_key, hz in edid_data.items():
            if any(part in device for part in mon_key.split("\\")):
                info["edid_declared_max_hz"] = hz
                break
        results.append(info)
    return results


# if __name__ == "__main__":
#     import json
#     caps = get_monitor_refresh_capabilities()
#     print(json.dumps(caps, indent=2))