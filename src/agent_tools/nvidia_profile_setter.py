"""
NVIDIA Profile Inspector setter.

Backs up the current profile, builds a modified .nip XML with optimal
settings, and imports it via NPI's -silentImport CLI flag.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from ..collectors.sub.nvidia_profile_dumper import (
    SETTING_IDS, TARGET_VALUES, find_npi_exe, calculate_fps_cap,
)
from ..utils.errors import SetterError
from ..utils.paths import get_temp_dir
from ..utils.action_logger import action_logger


def get_backups_dir():
    """Return ./lil_bro_backups/ (CWD-root). Delegates to utils.paths."""
    from ..utils.paths import get_backups_dir as _gbdir
    return _gbdir()


def _export_current_profile(npi_exe: str, dest_dir: str) -> str:
    """Run NPI -exportCustomized into dest_dir. Returns path to .nip file.

    NPI writes the .nip next to its own exe (ignores cwd), so we also look
    in ``Path(npi_exe).parent`` and move the file into ``dest_dir`` for
    normal cleanup.
    """
    result = subprocess.run(
        [npi_exe, "-exportCustomized"],
        cwd=dest_dir,
        capture_output=True,
        timeout=15,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise SetterError(f"NPI export failed (rc={result.returncode}): {stderr}")

    nip_files = list(Path(dest_dir).glob("*.nip"))
    if not nip_files:
        npi_dir = Path(npi_exe).parent
        fallback = list(npi_dir.glob("*.nip"))
        if fallback:
            target = Path(dest_dir) / fallback[0].name
            shutil.move(str(fallback[0]), str(target))
            return str(target)
        raise SetterError("NPI export produced no .nip file")
    return str(nip_files[0])


def backup_nvidia_profile(npi_exe: str) -> str:
    """Export current profile and copy to backup directory. Returns backup path."""
    backup_dir = get_backups_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"nv_profile_{timestamp}.nip"
    backup_path = backup_dir / backup_name

    with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmpdir:
        exported = _export_current_profile(npi_exe, tmpdir)
        shutil.copy2(exported, str(backup_path))

    action_logger.log_action("NPI Backup", "Created", str(backup_path))
    return str(backup_path)


def build_optimized_nip(source_nip_path: str, target_settings: dict[int, int]) -> str:
    """Parse source .nip XML, modify target settings, write to temp file.

    Args:
        source_nip_path: Path to the exported .nip file.
        target_settings: Maps SettingID (decimal int) → new SettingValue (int).
            If a SettingID doesn't exist in the source, it's appended to the
            Base Profile.

    Returns:
        Path to the modified .nip temp file (caller must clean up).
    """
    raw = Path(source_nip_path).read_bytes()
    text = raw.decode("utf-16")
    root = ET.fromstring(text)

    # Find the Base Profile (or first profile if no Base Profile exists)
    base_profile = None
    for profile in root.findall("Profile"):
        name = profile.findtext("ProfileName", "")
        if name == "Base Profile":
            base_profile = profile
            break
    if base_profile is None:
        profiles = root.findall("Profile")
        if not profiles:
            raise ValueError("No profiles found in .nip file")
        base_profile = profiles[0]

    settings_elem = base_profile.find("Settings")
    if settings_elem is None:
        settings_elem = ET.SubElement(base_profile, "Settings")

    # Build lookup of existing settings by SettingID
    existing: dict[int, ET.Element] = {}
    for ps in settings_elem.findall("ProfileSetting"):
        sid_text = ps.findtext("SettingID")
        if sid_text is not None:
            try:
                existing[int(sid_text)] = ps
            except ValueError:
                continue

    # Apply target settings
    for sid, new_val in target_settings.items():
        if sid in existing:
            val_elem = existing[sid].find("SettingValue")
            if val_elem is not None:
                val_elem.text = str(new_val)
        else:
            # Append new ProfileSetting element
            ps = ET.SubElement(settings_elem, "ProfileSetting")
            ET.SubElement(ps, "SettingNameInfo").text = " "
            ET.SubElement(ps, "SettingID").text = str(sid)
            ET.SubElement(ps, "SettingValue").text = str(new_val)
            ET.SubElement(ps, "ValueType").text = "Dword"

    # Write modified XML to temp file, preserving UTF-16 encoding
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".nip", dir=str(get_temp_dir()))
    os.close(tmp_fd)

    tree = ET.ElementTree(root)
    tree.write(tmp_path, encoding="utf-16", xml_declaration=True)

    return tmp_path


def apply_nvidia_profile(npi_exe: str, nip_path: str) -> tuple[bool, str]:
    """Import .nip via NPI CLI: nvidiaProfileInspector.exe -silentImport <path>.

    Returns (success, message).
    """
    try:
        result = subprocess.run(
            [npi_exe, "-silentImport", nip_path],
            capture_output=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return False, "NPI import timed out (15s)"

    if result.returncode == 0:
        return True, "Profile imported successfully"

    stderr = result.stderr.decode(errors="replace").strip()
    return False, f"NPI import failed (rc={result.returncode}): {stderr}"


def fix_nvidia_profile(
    specs: dict,
    refresh_hz: int | None = None,
    gpu_generation: str | None = None,
    pre_backup_path: str | None = None,
) -> bool:
    """Apply optimized NVIDIA driver profile.

    1. Backup current profile (skipped if pre_backup_path provided)
    2. Export fresh .nip
    3. Modify target settings
    4. Import via NPI -silentImport

    Args:
        specs: Full system specs dict.
        refresh_hz: Override for monitor refresh rate (auto-detected if None).
        gpu_generation: Override for GPU gen like "40" (auto-detected if None).
        pre_backup_path: Path to an already-created backup .nip. If provided,
            the internal backup step is skipped (avoids duplicate exports).

    Returns True on success.
    """
    from .nvidia_profile import _get_primary_refresh_hz, _get_gpu_generation, DLSS_PRESETS

    npi_exe = find_npi_exe()
    if npi_exe is None:
        raise FileNotFoundError("NVIDIA Profile Inspector binary not found")

    # 1. Backup (skip if caller already made one)
    if pre_backup_path is not None:
        backup_path = pre_backup_path
    else:
        backup_path = backup_nvidia_profile(npi_exe)
        action_logger.log_action("NPI Fix", "Backup created", backup_path)

    # 2. Export fresh .nip for modification
    with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmpdir:
        source_nip = _export_current_profile(npi_exe, tmpdir)

        # 3. Calculate target settings
        target: dict[int, int] = {}

        # G-Sync (7 settings)
        for key in [
            "gsync_global_feature", "gsync_global_mode", "gsync_app_mode",
            "gsync_app_state", "gsync_app_requested",
            "gsync_indicator_overlay", "gsync_support_indicator",
        ]:
            target[SETTING_IDS[key]] = TARGET_VALUES[key]

        # VSync (3 settings)
        for key in ["vsync", "vsync_tear_control", "vsync_smooth_afr"]:
            target[SETTING_IDS[key]] = TARGET_VALUES[key]

        # FPS cap
        if refresh_hz is None:
            refresh_hz = _get_primary_refresh_hz(specs)
        cap: int | None = None
        if refresh_hz and refresh_hz > 0:
            cap = calculate_fps_cap(refresh_hz)
            target[SETTING_IDS["fps_limiter_v3"]] = cap
            action_logger.log_action("NPI Fix", f"FPS cap: {cap}", f"{refresh_hz}Hz monitor")

        # ReBar driver toggle — only if BIOS ReBar is ON
        nvidia = specs.get("NVIDIA", [])
        bios_rebar = nvidia[0].get("ReBAR") if isinstance(nvidia, list) and nvidia else None
        if bios_rebar is True:
            target[SETTING_IDS["rebar_enable"]] = TARGET_VALUES["rebar_enable"]

        # DLSS preset
        if gpu_generation is None:
            gpu_name = nvidia[0].get("GPU", "") if isinstance(nvidia, list) and nvidia else ""
            gpu_generation = _get_gpu_generation(gpu_name)
        if gpu_generation and gpu_generation in DLSS_PRESETS:
            _, dlss_hex = DLSS_PRESETS[gpu_generation]
            target[SETTING_IDS["dlss_preset_profile"]] = TARGET_VALUES["dlss_preset_profile"]
            target[SETTING_IDS["dlss_preset_letter"]] = dlss_hex

        # Power management
        target[SETTING_IDS["power_mgmt"]] = TARGET_VALUES["power_mgmt"]

        # 4. Build modified .nip
        modified_nip = build_optimized_nip(source_nip, target)

    # 5. Import
    try:
        ok, msg = apply_nvidia_profile(npi_exe, modified_nip)
    finally:
        # Clean up temp modified .nip
        try:
            os.unlink(modified_nip)
        except OSError:
            pass

    if ok:
        changes = []
        if cap is not None:
            changes.append(f"FPS cap={cap}")
        if gpu_generation and gpu_generation in DLSS_PRESETS:
            changes.append(f"DLSS={DLSS_PRESETS[gpu_generation][0]}")
        if bios_rebar is True:
            changes.append("ReBar=ON")
        changes.extend(["G-Sync=ON", "VSync=ForceOn", "PowerMgmt=MaxPerf"])
        action_logger.log_action("NPI Fix", "Applied", ", ".join(changes))
        return True

    action_logger.log_action("NPI Fix", "FAILED", msg)
    raise SetterError(f"Profile import failed — original profile preserved at {backup_path}. Error: {msg}")
