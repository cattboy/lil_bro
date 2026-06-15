"""Fast registry/WMI snapshot for the GUI home dashboard.

Skips the expensive collectors (dxdiag, NVIDIA Profile Inspector,
nvidia-smi) so the home view can refresh every 5 seconds without
fighting the pipeline for system resources.

Per Eng Review (2026-05-05) we accept light duplication of registry-key
paths + WMI query strings (~30 lines) so existing collectors stay
untouched. T-012 tracks future consolidation via shared helpers.

Returns shape::

    {
        "power_plan": "Balanced" | "—",
        "game_mode":  "On" | "Off" | "—",
        "refresh_rate": "144 Hz" | "—",
        "mouse_hz": "1000" | "Not measured",
        "cpu_temp": "65°C" | "—",
        "gpu_temp": "58°C" | "—",
    }
"""

from __future__ import annotations

from typing import Any


_DASH = "—"


def quick_status_snapshot(lhm: Any | None = None) -> dict[str, str]:
    """Return a 6-card dashboard snapshot, swallowing any subsystem errors."""
    return {
        "power_plan":   _safe(_read_power_plan, _DASH),
        "game_mode":    _safe(_read_game_mode, _DASH),
        "refresh_rate": _safe(_read_refresh_rate, _DASH),
        "mouse_hz":     _safe(_read_mouse_hz, "Not measured"),
        "cpu_temp":     _safe(lambda: _read_temp(lhm, "cpu"), _DASH),
        "gpu_temp":     _safe(lambda: _read_temp(lhm, "gpu"), _DASH),
    }


# ── Individual reads ───────────────────────────────────────────────────


def _read_power_plan() -> str:
    """Active Windows power plan name via ``powercfg /getactivescheme``."""
    import re
    import subprocess

    from ..utils.subprocess_utils import CREATE_NO_WINDOW

    completed = subprocess.run(
        ["powercfg", "/getactivescheme"],
        capture_output=True,
        text=True,
        timeout=2,
        creationflags=CREATE_NO_WINDOW,
    )
    match = re.search(r"\((.+?)\)", completed.stdout)
    return match.group(1) if match else _DASH


def _read_game_mode() -> str:
    """Game Mode registry flag (HKCU\\Software\\Microsoft\\GameBar)."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"SOFTWARE\Microsoft\GameBar") as key:
            value, _ = winreg.QueryValueEx(key, "AutoGameModeEnabled")
            return "On" if value else "Off"
    except FileNotFoundError:
        return "On"  # default on Win10+


def _read_refresh_rate() -> str:
    """Primary monitor refresh rate via Win32 ``EnumDisplaySettingsW``."""
    import ctypes
    from ctypes import wintypes

    class DEVMODE(ctypes.Structure):
        _fields_ = [
            ("dmDeviceName", wintypes.WCHAR * 32),
            ("dmSpecVersion", wintypes.WORD),
            ("dmDriverVersion", wintypes.WORD),
            ("dmSize", wintypes.WORD),
            ("dmDriverExtra", wintypes.WORD),
            ("dmFields", wintypes.DWORD),
            ("_pad", ctypes.c_byte * 16),
            ("dmColor", wintypes.SHORT),
            ("dmDuplex", wintypes.SHORT),
            ("dmYResolution", wintypes.SHORT),
            ("dmTTOption", wintypes.SHORT),
            ("dmCollate", wintypes.SHORT),
            ("dmFormName", wintypes.WCHAR * 32),
            ("dmLogPixels", wintypes.WORD),
            ("dmBitsPerPel", wintypes.DWORD),
            ("dmPelsWidth", wintypes.DWORD),
            ("dmPelsHeight", wintypes.DWORD),
            ("dmDisplayFlags", wintypes.DWORD),
            ("dmDisplayFrequency", wintypes.DWORD),
        ]

    devmode = DEVMODE()
    devmode.dmSize = ctypes.sizeof(DEVMODE)
    ENUM_CURRENT_SETTINGS = -1
    ok = ctypes.windll.user32.EnumDisplaySettingsW(
        None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)
    )
    if not ok:
        return _DASH
    return f"{int(devmode.dmDisplayFrequency)} Hz"


def _read_mouse_hz() -> str:
    """Read the last measured mouse Hz from QSettings if any.

    The dashboard does not actively sample mouse polling — running a
    5-sec sample every 5-sec dashboard tick would be obnoxious. Instead
    we surface whatever the last in-pipeline mouse test wrote to
    QSettings under ``cache/mouse_hz``.
    """
    try:
        from PySide6.QtCore import QSettings
        qs = QSettings("lil_bro", "GUI")
        cached = qs.value("cache/mouse_hz")
        if cached is None:
            return "Not measured"
        return str(int(cached))
    except Exception:
        return "Not measured"


def _read_temp(lhm: Any | None, which: str) -> str:
    """Pull the latest CPU or GPU temperature from the LHM HTTP API."""
    if lhm is None:
        return _DASH
    try:
        cpu_c, gpu_c = lhm.read_latest()  # type: ignore[union-attr]
    except Exception:
        return _DASH
    value = cpu_c if which == "cpu" else gpu_c
    if value is None:
        return _DASH
    return f"{int(round(value))}°C"


def _safe(reader, fallback: str) -> str:
    try:
        return reader() or fallback
    except Exception:
        return fallback
