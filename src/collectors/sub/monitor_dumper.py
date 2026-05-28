import ctypes
from ctypes import wintypes

from src.utils.display_utils import DEVMODE, ENUM_CURRENT_SETTINGS, enum_raw_modes


# ── EnumDisplaySettings approach ──────────────────────────────────────────────

def enum_display_modes(device_name: str | None = None) -> list[dict]:
    """
    Returns all supported display modes for a given device (e.g. '\\\\.\\DISPLAY1').
    If device_name is None, uses the primary display.
    Crucially this iterates ALL modes the driver exposes, not just the current one.
    """
    return [
        {
            "width":      dm.dmPelsWidth,
            "height":     dm.dmPelsHeight,
            "refresh_hz": dm.dmDisplayFrequency,
            "bit_depth":  dm.dmBitsPerPel,
        }
        for dm in enum_raw_modes(device_name)
    ]

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

_DISPLAY_DEVICE_ACTIVE = 0x00000001
_DISPLAY_DEVICE_MIRRORING_DRIVER = 0x00000008


def _enum_display_devices(require_active: bool, exclude_mirror: bool = True) -> list[str]:
    """Walks ``EnumDisplayDevicesW`` with configurable filters.

    Hybrid-GPU laptops often leave the integrated panel without the
    ACTIVE flag even though it's rendering. ``require_active=False`` is
    the laptop fallback path.
    """
    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ("cb",           wintypes.DWORD),
            ("DeviceName",   ctypes.c_wchar * 32),
            ("DeviceString", ctypes.c_wchar * 128),
            ("StateFlags",   wintypes.DWORD),
            ("DeviceID",     ctypes.c_wchar * 128),
            ("DeviceKey",    ctypes.c_wchar * 128),
        ]

    user32 = ctypes.windll.user32
    devices: list[str] = []
    i = 0
    while True:
        dd = DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        flags = dd.StateFlags
        if exclude_mirror and (flags & _DISPLAY_DEVICE_MIRRORING_DRIVER):
            i += 1
            continue
        if require_active and not (flags & _DISPLAY_DEVICE_ACTIVE):
            i += 1
            continue
        devices.append(dd.DeviceName)
        i += 1
    return devices


def get_all_displays() -> list[str]:
    """Returns device names like ['\\\\.\\DISPLAY1', '\\\\.\\DISPLAY2', ...].

    Tries strict (ACTIVE-only) first, then falls back to all non-mirror
    display devices to catch integrated panels on hybrid-GPU laptops.
    """
    devices = _enum_display_devices(require_active=True, exclude_mirror=True)
    if devices:
        return devices
    return _enum_display_devices(require_active=False, exclude_mirror=True)


# ── EDID cross-check (optional but useful for validation) ─────────────────────

def get_edid_max_refresh_from_registry() -> list[dict]:
    """
    Reads raw EDID bytes from the Windows registry and extracts the
    monitor-declared max vertical refresh from the Monitor Range Limits
    descriptor (tag 0xFD). This is the hardware ground truth.
    """
    import winreg
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

def _wmi_fallback_capabilities() -> list[dict]:
    """Last-resort enumeration via WMI Win32_VideoController.

    Used when ``EnumDisplayDevicesW`` returns nothing (some laptop
    iGPU configurations). WMI typically reports the current resolution's
    refresh as both current and max, so the card may say "optimal"
    without true panel-max knowledge — better than no card at all.
    """
    try:
        import wmi  # type: ignore[import]
        c = wmi.WMI()
        out: list[dict] = []
        for v in c.Win32_VideoController():
            cur = int(getattr(v, "CurrentRefreshRate", 0) or 0)
            mx = int(getattr(v, "MaxRefreshRate", 0) or 0) or cur
            w = int(getattr(v, "CurrentHorizontalResolution", 0) or 0)
            h = int(getattr(v, "CurrentVerticalResolution", 0) or 0)
            if cur <= 0 and mx <= 0:
                continue
            name = str(getattr(v, "Name", "Unknown adapter"))
            rates = sorted({r for r in (cur, mx) if r > 0}, reverse=True)
            out.append({
                "device": f"WMI:{name}",
                "max_refresh_hz": mx or cur,
                "at_resolution": f"{w}x{h}" if w and h else "",
                "current_refresh_hz": cur,
                "all_refresh_rates": rates,
                "edid_declared_max_hz": None,
                "source": "wmi",
            })
        return out
    except Exception:
        return []


def get_monitor_refresh_capabilities() -> list[dict]:
    displays = get_all_displays()
    results: list[dict] = []
    edid_data = {e["monitor"]: e.get("edid_max_refresh_hz")
                 for e in get_edid_max_refresh_from_registry()
                 if "monitor" in e}

    for device in displays:
        info = get_max_refresh_for_device(device)
        info["device"] = device
        info["source"] = "winapi"
        # Attach EDID ground-truth if we can match it (best-effort name match)
        for mon_key, hz in edid_data.items():
            if any(part in device for part in mon_key.split("\\")):
                info["edid_declared_max_hz"] = hz
                break
        results.append(info)

    if not results:
        results = _wmi_fallback_capabilities()
    return results


# if __name__ == "__main__":
#     import json
#     caps = get_monitor_refresh_capabilities()
#     print(json.dumps(caps, indent=2))