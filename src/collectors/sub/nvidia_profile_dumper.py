"""
NVIDIA Profile Inspector collector.

Exports the current NVIDIA driver profile via NPI CLI and parses
the .nip XML to extract key driver settings (G-Sync, VSync, FPS cap,
ReBar, DLSS preset, power management).
"""

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from ...utils.paths import get_appdata_dir
from ...utils.action_logger import action_logger

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_NPI_SEARCH_PATHS = [
    # 1. PyInstaller frozen bundle — sys._MEIPASS/tools/nvidiaProfileInspector.exe
    os.path.join(getattr(sys, "_MEIPASS", _PROJECT_ROOT), "tools", "nvidiaProfileInspector.exe"),
    # 2. %APPDATA%\lil_bro\tools\ — extraction fallback for long _MEIPASS paths
    os.path.join(str(get_appdata_dir()), "tools", "nvidiaProfileInspector.exe"),
    # 3. Source-tree dev path
    os.path.join(_PROJECT_ROOT, "tools", "nvidiaProfileInspector", "nvidiaProfileInspector.exe"),
]

# Canonical setting IDs (decimal) from NPI_CustomSettingNames.xml hex codes.
# The .nip XML uses decimal SettingIDs — these are the converted values.
SETTING_IDS: dict[str, int] = {
    "gsync_global_feature":     278196567,   # 0x1094F157
    "gsync_global_mode":        278196727,   # 0x1094F1F7
    "gsync_app_mode":           294973784,   # 0x1194F158
    "gsync_app_state":          279476687,   # 0x10A879CF
    "gsync_app_requested":      279476652,   # 0x10A879AC
    "gsync_indicator_overlay":  268604728,   # 0x10029538
    "gsync_support_indicator":  9303312,     # 0x008DF510
    "vsync":                    11041231,    # 0x00A879CF
    "vsync_tear_control":       5912412,     # 0x005A375C
    "vsync_smooth_afr":         270198627,   # 0x101AE763
    "fps_limiter_v3":           277041154,   # 0x10835002
    "rebar_enable":             983226,      # 0x000F00BA
    "dlss_preset_profile":      6505105,     # 0x00634291
    "dlss_preset_letter":       283385331,   # 0x10E41DF3
    "power_mgmt":               274029608,   # 0x10555C28
}

# Target values for optimal gaming configuration.
TARGET_VALUES: dict[str, int] = {
    "gsync_global_feature":     1,           # On
    "gsync_global_mode":        1,           # Fullscreen only
    "gsync_app_mode":           1,           # Fullscreen only
    "gsync_app_state":          0,           # Allow
    "gsync_app_requested":      0,           # Allow
    "gsync_indicator_overlay":  0,           # Off
    "gsync_support_indicator":  0,           # Off
    "vsync":                    0x47814940,  # Force on (1199655232)
    "vsync_tear_control":       0x96861077,  # Standard (2525368439)
    "vsync_smooth_afr":         0,           # Off
    # fps_limiter_v3 is calculated per monitor Hz — not a static target
    "rebar_enable":             1,           # Enabled
    "dlss_preset_profile":      2,           # Custom
    # dlss_preset_letter depends on GPU generation
    "power_mgmt":               1,           # Prefer Maximum Performance
}

# DLSS preset letter mapping: hex value → letter name
DLSS_LETTER_MAP: dict[int, str] = {
    0: "N/A", 1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F",
    7: "G", 8: "H", 9: "I", 10: "J", 11: "K", 12: "L", 13: "M",
    14: "N", 15: "O", 0x00FFFFFF: "recommended",
}


def find_npi_exe() -> str | None:
    """Locate nvidiaProfileInspector.exe in search paths."""
    for path in _NPI_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None


def parse_nip(nip_path: str) -> dict[int, int]:
    """Parse a .nip XML file and return {SettingID: SettingValue} mapping.

    The .nip format is UTF-16 encoded XML with structure:
      <ArrayOfProfile> / <Profile> / <Settings> / <ProfileSetting>
    Each ProfileSetting has <SettingID> (decimal int) and <SettingValue> (decimal int).
    """
    raw = Path(nip_path).read_bytes()
    text = raw.decode("utf-16")
    root = ET.fromstring(text)

    settings: dict[int, int] = {}
    for profile in root.findall("Profile"):
        for ps in profile.findall("Settings/ProfileSetting"):
            sid_text = ps.findtext("SettingID")
            val_text = ps.findtext("SettingValue")
            if sid_text is not None and val_text is not None:
                try:
                    settings[int(sid_text)] = int(val_text)
                except ValueError:
                    continue
    return settings


def _interpret_gsync(raw: dict[int, int]) -> bool | None:
    """True if G-Sync global feature is ON."""
    val = raw.get(SETTING_IDS["gsync_global_feature"])
    if val is None:
        return None
    return val == 1


def _interpret_vsync(raw: dict[int, int]) -> str | None:
    """Interpret VSync mode from setting value."""
    val = raw.get(SETTING_IDS["vsync"])
    if val is None:
        return None
    if val == 0x47814940:
        return "force_on"
    if val == 0:
        return "off"
    return f"other_{val}"


def _interpret_fps_cap(raw: dict[int, int]) -> int | None:
    """Current FPS cap value, or None if not set."""
    val = raw.get(SETTING_IDS["fps_limiter_v3"])
    return val


def _interpret_rebar(raw: dict[int, int]) -> bool | None:
    """True if driver-side ReBar toggle is enabled."""
    val = raw.get(SETTING_IDS["rebar_enable"])
    if val is None:
        return None
    return val == 1


def _interpret_dlss(raw: dict[int, int]) -> str | None:
    """Current DLSS preset letter name."""
    val = raw.get(SETTING_IDS["dlss_preset_letter"])
    if val is None:
        return None
    return DLSS_LETTER_MAP.get(val, f"unknown_{val}")


def _interpret_power_mgmt(raw: dict[int, int]) -> str | None:
    """Interpret power management mode."""
    val = raw.get(SETTING_IDS["power_mgmt"])
    if val is None:
        return None
    if val == 1:
        return "max_performance"
    if val == 0:
        return "adaptive"
    return f"other_{val}"


def get_nvidia_profile() -> dict[str, Any]:
    """Export current NVIDIA profile via NPI CLI and parse key settings.

    Returns a dict with parsed settings. On failure, returns a dict with
    ``available=False`` or an ``error`` key describing the failure.
    """
    npi_exe = find_npi_exe()
    if npi_exe is None:
        action_logger.log_action("NPI Collector", "Skipped", "binary not found", outcome="SKIP")
        return {"available": False, "reason": "NPI binary not found"}

    action_logger.log_action("NPI Collector", "Invoked", npi_exe)
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            result = subprocess.run(
                [npi_exe, "-exportCustomized"],
                cwd=tmpdir,
                capture_output=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            action_logger.log_action("NPI Collector", "Timeout", "export timed out after 15s", outcome="FAIL")
            return {"available": True, "error": "NPI export timed out"}
        except FileNotFoundError:
            action_logger.log_action("NPI Collector", "Skipped", "binary not found at runtime", outcome="SKIP")
            return {"available": False, "reason": "NPI binary not found"}

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            # rc 3221225477 (0xC0000005) + DrsSession NullRef = NVAPI failed to init (no NVIDIA GPU)
            if result.returncode == 3221225477 and "DrsSession" in stderr:
                action_logger.log_action(
                    "NPI Collector", "Skipped",
                    "no NVIDIA GPU detected — NVAPI failed to initialize", outcome="SKIP",
                )
                return {"available": False, "reason": "No NVIDIA GPU detected"}
            action_logger.log_action("NPI Collector", "Failed", f"rc={result.returncode}: {stderr}", outcome="FAIL")
            return {"available": True, "error": f"NPI export failed (rc={result.returncode}): {stderr}"}

        nip_files = list(Path(tmpdir).glob("*.nip"))
        if not nip_files:
            action_logger.log_action("NPI Collector", "Failed", "no .nip file produced", outcome="FAIL")
            return {"available": True, "error": "NPI export produced no .nip file"}

        try:
            raw_settings = parse_nip(str(nip_files[0]))
        except (ET.ParseError, UnicodeDecodeError, ValueError) as e:
            action_logger.log_action("NPI Collector", "ParseError", str(e), outcome="FAIL")
            return {"available": True, "error": f"Failed to parse .nip XML: {e}"}

    return {
        "available": True,
        "gsync_enabled": _interpret_gsync(raw_settings),
        "vsync_mode": _interpret_vsync(raw_settings),
        "fps_cap": _interpret_fps_cap(raw_settings),
        "rebar_driver": _interpret_rebar(raw_settings),
        "dlss_preset": _interpret_dlss(raw_settings),
        "power_mgmt": _interpret_power_mgmt(raw_settings),
        "raw_settings": raw_settings,
    }
