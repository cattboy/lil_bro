"""Shared Win32 display utilities — DEVMODE struct and raw mode enumeration.

Both monitor_dumper (collector) and display_setter (agent tool) need the same
DEVMODE ctypes struct and the low-level EnumDisplaySettings loop. This module
is the single canonical definition; callers import from here.
"""

import ctypes
from ctypes import wintypes

ENUM_CURRENT_SETTINGS  = -1
ENUM_REGISTRY_SETTINGS = -2


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",         ctypes.c_wchar * 32),
        ("dmSpecVersion",        wintypes.WORD),
        ("dmDriverVersion",      wintypes.WORD),
        ("dmSize",               wintypes.WORD),
        ("dmDriverExtra",        wintypes.WORD),
        ("dmFields",             wintypes.DWORD),
        ("dmPositionX",          ctypes.c_long),
        ("dmPositionY",          ctypes.c_long),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor",              ctypes.c_short),
        ("dmDuplex",             ctypes.c_short),
        ("dmYResolution",        ctypes.c_short),
        ("dmTTOption",           ctypes.c_short),
        ("dmCollate",            ctypes.c_short),
        ("dmFormName",           ctypes.c_wchar * 32),
        ("dmLogPixels",          wintypes.WORD),
        ("dmBitsPerPel",         wintypes.DWORD),
        ("dmPelsWidth",          wintypes.DWORD),
        ("dmPelsHeight",         wintypes.DWORD),
        ("dmDisplayFlags",       wintypes.DWORD),
        ("dmDisplayFrequency",   wintypes.DWORD),
        ("dmICMMethod",          wintypes.DWORD),
        ("dmICMIntent",          wintypes.DWORD),
        ("dmMediaType",          wintypes.DWORD),
        ("dmDitherType",         wintypes.DWORD),
        ("dmReserved1",          wintypes.DWORD),
        ("dmReserved2",          wintypes.DWORD),
        ("dmPanningWidth",       wintypes.DWORD),
        ("dmPanningHeight",      wintypes.DWORD),
    ]


def enum_raw_modes(device_name: str | None = None) -> list:
    """Return all DEVMODE structs supported by the given display adapter.

    Args:
        device_name: Win32 device name e.g. '\\\\.\\DISPLAY1'. None uses the
                     primary display (EnumDisplaySettingsW interprets NULL as primary).

    Returns:
        List of DEVMODE objects, one per supported mode.
    """
    modes = []
    i = 0
    while True:
        dm = DEVMODE()
        dm.dmSize = ctypes.sizeof(DEVMODE)
        if not ctypes.windll.user32.EnumDisplaySettingsW(device_name, i, ctypes.byref(dm)):
            break
        modes.append(dm)
        i += 1
    return modes
