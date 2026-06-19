"""HDR status collector — DisplayConfig advanced-color + Auto HDR registry + OS build.

Net-new from the refresh-rate collector (``monitor_dumper.py``): HDR capability is
read via the Windows **DisplayConfig** API (``QueryDisplayConfig`` +
``DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO``), which reflects what the real
GPU+driver+cable+mode pipeline will deliver — not what EDID merely claims. Auto
HDR state is read from the registry (``DirectXUserGlobalSettings``), and the
Windows build comes from the registry ``CurrentBuildNumber`` (NOT
``sys.getwindowsversion()``, which caps under the PyInstaller bundle).

Output contract (``specs["HDRStatus"]``), consumed by ``agent_tools/hdr.py``::

    {
      "determined": bool,        # False -> dashboard HIDES the card
      "error": str | None,       # failing-path note for the debug log
      "os_build": int,
      "is_win11": bool,          # build >= 22000
      "auto_hdr_enabled": bool | None,
      "auto_hdr_raw": str | None,    # raw DirectXUserGlobalSettings (future write)
      "has_per_app_overrides": bool,
      "displays": [
        {"device": "\\\\.\\DISPLAY1", "is_primary": bool,
         "hdr_capable": bool, "hdr_enabled": bool, "source": "displayconfig"},
      ],
    }

All reads are pure (no writes). The Auto HDR / RTX HDR one-click writes are
deferred to TODOS T-039 / T-040.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from src.utils.debug_logger import get_debug_logger

# ── DisplayConfig constants ───────────────────────────────────────────────────

ERROR_SUCCESS = 0
QDC_ONLY_ACTIVE_PATHS = 0x00000002
DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME = 1
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9
DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO_2 = 12  # Win11 24H2 successor
_DISPLAY_DEVICE_PRIMARY_DEVICE = 0x00000004
WIN11_MIN_BUILD = 22000


class _LUID(ctypes.Structure):
    _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]


class _RATIONAL(ctypes.Structure):
    _fields_ = [("Numerator", wintypes.UINT), ("Denominator", wintypes.UINT)]


class _PATH_SOURCE_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", _LUID),
        ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT),
        ("statusFlags", wintypes.UINT),
    ]


class _PATH_TARGET_INFO(ctypes.Structure):
    _fields_ = [
        ("adapterId", _LUID),
        ("id", wintypes.UINT),
        ("modeInfoIdx", wintypes.UINT),
        ("outputTechnology", wintypes.UINT),
        ("rotation", wintypes.UINT),
        ("scaling", wintypes.UINT),
        ("refreshRate", _RATIONAL),
        ("scanLineOrdering", wintypes.UINT),
        ("targetAvailable", wintypes.BOOL),
        ("statusFlags", wintypes.UINT),
    ]


class _PATH_INFO(ctypes.Structure):
    _fields_ = [
        ("sourceInfo", _PATH_SOURCE_INFO),
        ("targetInfo", _PATH_TARGET_INFO),
        ("flags", wintypes.UINT),
    ]


class _MODE_INFO(ctypes.Structure):
    # 4 + 4 + 8 + 48 = 64 bytes. The 48-byte blob is the targetMode/sourceMode/
    # desktopImageInfo union (largest member = DISPLAYCONFIG_TARGET_MODE = 48B).
    # We never read it; we only need the correct size for QueryDisplayConfig.
    _fields_ = [
        ("infoType", wintypes.UINT),
        ("id", wintypes.UINT),
        ("adapterId", _LUID),
        ("_modeUnion", ctypes.c_ubyte * 48),
    ]


class _DEVICE_INFO_HEADER(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.INT),
        ("size", wintypes.UINT),
        ("adapterId", _LUID),
        ("id", wintypes.UINT),
    ]


class _GET_ADVANCED_COLOR_INFO(ctypes.Structure):
    _fields_ = [
        ("header", _DEVICE_INFO_HEADER),
        ("value", wintypes.UINT),  # bit0=advancedColorSupported, bit1=advancedColorEnabled
        ("colorEncoding", wintypes.UINT),
        ("bitsPerColorChannel", wintypes.UINT),
    ]


class _SOURCE_DEVICE_NAME(ctypes.Structure):
    _fields_ = [
        ("header", _DEVICE_INFO_HEADER),
        ("viewGdiDeviceName", ctypes.c_wchar * 32),  # CCHDEVICENAME
    ]


def _primary_device_name() -> str | None:
    """Return the GDI device name (e.g. '\\\\.\\DISPLAY1') flagged primary."""
    class DISPLAY_DEVICE(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("DeviceName", ctypes.c_wchar * 32),
            ("DeviceString", ctypes.c_wchar * 128),
            ("StateFlags", wintypes.DWORD),
            ("DeviceID", ctypes.c_wchar * 128),
            ("DeviceKey", ctypes.c_wchar * 128),
        ]

    user32 = ctypes.windll.user32
    i = 0
    while True:
        dd = DISPLAY_DEVICE()
        dd.cb = ctypes.sizeof(dd)
        if not user32.EnumDisplayDevicesW(None, i, ctypes.byref(dd), 0):
            break
        if dd.StateFlags & _DISPLAY_DEVICE_PRIMARY_DEVICE:
            return dd.DeviceName
        i += 1
    return None


def _query_advanced_color(adapter_id: _LUID, target_id: int) -> dict | None:
    """DisplayConfigGetDeviceInfo for one target. Tries the established
    GET_ADVANCED_COLOR_INFO (type 9); on failure retries the 24H2 successor
    (type 12) reading the same supported/enabled bits. Returns
    {hdr_capable, hdr_enabled} or None if both calls error."""
    user32 = ctypes.windll.user32
    for info_type in (
        DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO,
        DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO_2,
    ):
        info = _GET_ADVANCED_COLOR_INFO()
        info.header.type = info_type
        info.header.size = ctypes.sizeof(_GET_ADVANCED_COLOR_INFO)
        info.header.adapterId = adapter_id
        info.header.id = target_id
        if user32.DisplayConfigGetDeviceInfo(ctypes.byref(info)) == ERROR_SUCCESS:
            return {
                "hdr_capable": bool(info.value & 0x1),
                "hdr_enabled": bool((info.value >> 1) & 0x1),
            }
    return None


def _query_source_name(adapter_id: _LUID, source_id: int) -> str | None:
    """Map a path source to its GDI device name (e.g. '\\\\.\\DISPLAY1')."""
    user32 = ctypes.windll.user32
    name = _SOURCE_DEVICE_NAME()
    name.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_SOURCE_NAME
    name.header.size = ctypes.sizeof(_SOURCE_DEVICE_NAME)
    name.header.adapterId = adapter_id
    name.header.id = source_id
    if user32.DisplayConfigGetDeviceInfo(ctypes.byref(name)) == ERROR_SUCCESS:
        return name.viewGdiDeviceName or None
    return None


def _displayconfig_hdr() -> list[dict] | None:
    """Enumerate active display paths and read advanced-color (HDR) state.

    Returns a per-display list (device + hdr_capable + hdr_enabled), or None if
    the DisplayConfig query failed entirely (the card hides on None)."""
    user32 = ctypes.windll.user32
    num_paths = wintypes.UINT(0)
    num_modes = wintypes.UINT(0)
    if user32.GetDisplayConfigBufferSizes(
        QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_paths), ctypes.byref(num_modes)
    ) != ERROR_SUCCESS:
        return None

    paths = (_PATH_INFO * num_paths.value)()
    modes = (_MODE_INFO * num_modes.value)()
    if user32.QueryDisplayConfig(
        QDC_ONLY_ACTIVE_PATHS,
        ctypes.byref(num_paths), paths,
        ctypes.byref(num_modes), modes,
        None,
    ) != ERROR_SUCCESS:
        return None

    primary = _primary_device_name()
    results: list[dict] = []
    seen: set[str] = set()
    for i in range(num_paths.value):
        path = paths[i]
        color = _query_advanced_color(path.targetInfo.adapterId, path.targetInfo.id)
        if color is None:
            continue
        device = _query_source_name(path.sourceInfo.adapterId, path.sourceInfo.id) or f"DISPLAY{i+1}"
        if device in seen:
            continue
        seen.add(device)
        results.append({
            "device": device,
            "is_primary": (device == primary),
            "hdr_capable": color["hdr_capable"],
            "hdr_enabled": color["hdr_enabled"],
            "source": "displayconfig",
        })
    return results or None


# ── Auto HDR registry (READ only) ─────────────────────────────────────────────

_AUTO_HDR_KEY = r"Software\Microsoft\DirectX\UserGpuPreferences"
_AUTO_HDR_VALUE = "DirectXUserGlobalSettings"


def parse_auto_hdr(raw: str | None) -> bool | None:
    """Parse the AutoHDREnable token out of the semicolon-delimited
    DirectXUserGlobalSettings string. Returns None when the token is absent
    (the global default has never been set). Pure — unit-testable."""
    if not raw:
        return None
    for part in raw.split(";"):
        if "=" not in part:
            continue
        key, _, val = part.partition("=")
        if key.strip() == "AutoHDREnable":
            return val.strip() == "1"
    return None


def _read_auto_hdr() -> tuple[bool | None, str | None, bool]:
    """Return (auto_hdr_enabled, raw_global_string, has_per_app_overrides)."""
    import winreg

    raw: str | None = None
    has_overrides = False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _AUTO_HDR_KEY) as key:
            _, value_count, _ = winreg.QueryInfoKey(key)
            for idx in range(value_count):
                name, data, _ = winreg.EnumValue(key, idx)
                if name == _AUTO_HDR_VALUE:
                    raw = data
                elif name:  # any other value = a per-exe override
                    has_overrides = True
    except FileNotFoundError:
        pass
    except OSError:
        get_debug_logger().warning("Auto HDR registry read failed", exc_info=True)
    return parse_auto_hdr(raw), raw, has_overrides


def _windows_build() -> int:
    """Windows build number from the registry (reliable under the PyInstaller
    bundle, unlike sys.getwindowsversion which reports the manifest version)."""
    import winreg

    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            value, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
            return int(value)
    except (FileNotFoundError, OSError, ValueError):
        get_debug_logger().warning("CurrentBuildNumber read failed", exc_info=True)
        return 0


# ── Main entry point ──────────────────────────────────────────────────────────


def get_hdr_status() -> dict:
    """Collect HDR status. ``determined=False`` (card hidden) when DisplayConfig
    can't read advanced-color state; ``error`` names the failing path so the
    debug log is greppable in the field."""
    try:
        displays = _displayconfig_hdr()
    except Exception:
        get_debug_logger().error("DisplayConfig HDR query raised", exc_info=True)
        displays = None

    if not displays:
        msg = "DisplayConfig returned no advanced-color data — possible 24H2 struct or no active HDR path"
        get_debug_logger().warning("HDR undetermined: %s", msg)
        return {"determined": False, "error": msg, "os_build": 0, "is_win11": False,
                "auto_hdr_enabled": None, "auto_hdr_raw": None,
                "has_per_app_overrides": False, "displays": []}

    auto_enabled, auto_raw, has_overrides = _read_auto_hdr()
    build = _windows_build()
    return {
        "determined": True,
        "error": None,
        "os_build": build,
        "is_win11": build >= WIN11_MIN_BUILD,
        "auto_hdr_enabled": auto_enabled,
        "auto_hdr_raw": auto_raw,
        "has_per_app_overrides": has_overrides,
        "displays": displays,
    }
