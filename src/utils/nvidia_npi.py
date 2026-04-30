"""
NVIDIA Profile Inspector — shared domain knowledge and export helper.

Owns the NPI binary search paths, canonical SettingID/value constants, the
Blur Busters FPS cap formula, and the single shared `export_current_profile`
helper used by both the collector (nvidia_profile_dumper) and the
agent_tool (nvidia_profile_setter).
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from .action_logger import action_logger
from .errors import SetterError
from .nip_io import parse_nip_with_retry, wait_for_nip_ready
from .paths import get_lil_bro_dir

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_NPI_SEARCH_PATHS = [
    # 1. PyInstaller frozen bundle — sys._MEIPASS/tools/nvidiaProfileInspector.exe
    os.path.join(getattr(sys, "_MEIPASS", _PROJECT_ROOT), "tools", "nvidiaProfileInspector.exe"),
    # 2. ./lil_bro/tools/ — CWD-relative fallback for long _MEIPASS paths
    os.path.join(str(get_lil_bro_dir()), "tools", "nvidiaProfileInspector.exe"),
    # 3. Source-tree dev path
    os.path.join(_PROJECT_ROOT, "tools", "nvidiaProfileInspector", "nvidiaProfileInspector.exe"),
]

# Canonical setting IDs from docs/NPI_CustomSettingNames.xml.
# Hex literals match the XML's HexSettingID for cross-referencing.
SETTING_IDS: dict[str, int] = {
    "gsync_global_feature":     0x1094F157,  # GSYNC - Global Feature
    "gsync_global_mode":        0x1094F1F7,  # GSYNC - Global Mode
    "gsync_app_mode":           0x1194F158,  # GSYNC - Application Mode
    "gsync_app_state":          0x10A879CF,  # GSYNC - Application State
    "gsync_app_requested":      0x10A879AC,  # GSYNC - Application Requested State
    "gsync_indicator_overlay":  0x10029538,  # GSYNC - Indicator Overlay
    "gsync_support_indicator":  0x008DF510,  # GSYNC - Support Indicator Overlay
    "vsync":                    0x00A879CF,  # Vertical Sync
    "vsync_tear_control":       0x005A375C,  # Vertical Sync - Tear Control
    "vsync_smooth_afr":         0x101AE763,  # Vertical Sync - Smooth AFR Behavior
    "fps_limiter_v3":           0x10835002,  # Frame Rate Limiter V3
    "rebar_enable":             0x000F00BA,  # rBAR - Enable
    "dlss_preset_profile":      0x00634291,  # DLSS - Forced Model Preset Profile
    "dlss_preset_letter":       0x10E41DF3,  # DLSS - Forced Preset Letter
    "power_mgmt":               0x1057EB71,  # Power Management - Mode
}

# Target values for optimal gaming configuration.
# fps_limiter_v3 is calculated per monitor Hz (see calculate_fps_cap).
# dlss_preset_letter depends on GPU generation (see DLSS_PRESETS).
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
    "rebar_enable":             1,           # Enabled
    "dlss_preset_profile":      2,           # Custom
    "power_mgmt":               1,           # Prefer Maximum Performance
}

# DLSS preset letter mapping: hex value → letter name.
DLSS_LETTER_MAP: dict[int, str] = {
    0: "N/A", 1: "A", 2: "B", 3: "C", 4: "D", 5: "E", 6: "F",
    7: "G", 8: "H", 9: "I", 10: "J", 11: "K", 12: "L", 13: "M",
    14: "N", 15: "O", 0x00FFFFFF: "recommended",
}

# GPU generation → recommended DLSS preset (letter, hex value).
DLSS_PRESETS: dict[str, tuple[str, int]] = {
    "50": ("L", 0x0C),   # RTX 50-series — Transformer Gen 2
    "40": ("L", 0x0C),   # RTX 40-series — Transformer Gen 2
    "30": ("K", 0x0B),   # RTX 30-series — Transformer Gen 1
    "20": ("K", 0x0B),   # RTX 20-series — Transformer Gen 1
}


def calculate_fps_cap(refresh_hz: int) -> int:
    """Blur Busters formula: cap = round(refresh_hz - refresh_hz^2 / 4096).

    Produces 226 for 240Hz, 328 for 360Hz, 424 for 480Hz.

    Note: the formula goes negative for Hz > ~4096, which as a DWORD would wrap
    to ~4 billion (effectively disabling the cap). No commercial monitor exceeds
    ~600Hz today so no upper-bound guard is needed.
    """
    return round(refresh_hz - (refresh_hz * refresh_hz / 4096))


def find_npi_exe() -> str | None:
    """Locate nvidiaProfileInspector.exe in search paths."""
    for path in _NPI_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None


def export_current_profile(npi_exe: str, dest_dir: str) -> tuple[str, dict[int, int]]:
    """Run NPI -exportCustomized and return ``(nip_path, raw_settings)``.

    NPI must run from its own directory (it loads adjacent DLLs via relative
    paths). The .nip is written there, waited on for write completion, then
    moved into ``dest_dir`` so the caller's TemporaryDirectory handles cleanup.

    Raises ``SetterError`` on subprocess failure, missing .nip, or readiness
    timeout. Parse failures propagate from ``parse_nip_with_retry``.
    """
    npi_dir = Path(npi_exe).parent

    result = subprocess.run(
        [npi_exe, "-exportCustomized"],
        cwd=str(npi_dir),
        capture_output=True,
        timeout=30,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise SetterError(f"NPI export failed (rc={result.returncode}): {stderr}")

    nip_files = list(npi_dir.glob("*.nip"))
    action_logger.log_action(
        "NPI Export", "Glob",
        f"dir={npi_dir} count={len(nip_files)} names={[p.name for p in nip_files]}",
    )
    if not nip_files:
        try:
            listing = [p.name for p in npi_dir.iterdir()]
        except OSError as e:
            listing = f"<iterdir failed: {e}>"
        raise SetterError(f"NPI export produced no .nip file (dir contents: {listing})")

    # Wait for NPI's child writer to finish in-place BEFORE moving. Moving a
    # file with an open writer handle can orphan bytes on Windows.
    original = nip_files[0]
    wait_for_nip_ready(str(original))

    target = Path(dest_dir) / original.name
    shutil.move(str(original), str(target))

    raw_settings = parse_nip_with_retry(str(target))
    return str(target), raw_settings
