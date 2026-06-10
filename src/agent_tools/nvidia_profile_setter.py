"""
NVIDIA Profile Inspector setter.

Backs up the current profile, builds a modified .nip XML with optimal
settings, and imports it via NPI's -silentImport CLI flag.
"""

import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

from ..config import config
from ..utils.action_logger import action_logger
from ..utils.dlss_presets import get_preset
from ..utils.errors import SetterError
from ..utils.nvidia_npi import (
    SETTING_IDS,
    TARGET_VALUES,
    calculate_fps_cap,
    export_current_profile,
    find_npi_exe,
)
from ..utils.paths import get_backups_dir, get_temp_dir
from ..utils.subprocess_utils import CREATE_NO_WINDOW
from .nvidia_profile import _get_primary_refresh_hz


def backup_nvidia_profile(npi_exe: str) -> str:
    """Export current profile and copy to backup directory. Returns backup path."""
    backup_dir = get_backups_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"lil_bro_nv_profile_{timestamp}.nip"
    backup_path = backup_dir / backup_name

    with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmpdir:
        exported, _ = export_current_profile(npi_exe, tmpdir)
        shutil.copy2(exported, str(backup_path))

    action_logger.log_action("NPI Backup", "Created", str(backup_path))
    return str(backup_path)


def build_optimized_nip(source_nip_path: str, target_settings: dict[int, int]) -> str:
    """Parse source .nip XML, modify target settings, write to temp file.

    Args:
        source_nip_path: Path to the exported .nip file.
        target_settings: Maps SettingID (decimal int) to new SettingValue (int).
            If a SettingID doesn't exist in the source, it's appended to the
            Base Profile.

    Returns:
        Path to the modified .nip temp file (caller must clean up).
    """
    raw = Path(source_nip_path).read_bytes()
    text = raw.decode("utf-16")
    root = ET.fromstring(text)

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

    existing: dict[int, ET.Element] = {}
    for ps in settings_elem.findall("ProfileSetting"):
        sid_text = ps.findtext("SettingID")
        if sid_text is not None:
            try:
                existing[int(sid_text)] = ps
            except ValueError:
                continue

    for sid, new_val in target_settings.items():
        if sid in existing:
            val_elem = existing[sid].find("SettingValue")
            if val_elem is not None:
                val_elem.text = str(new_val)
        else:
            ps = ET.SubElement(settings_elem, "ProfileSetting")
            ET.SubElement(ps, "SettingNameInfo").text = " "
            ET.SubElement(ps, "SettingID").text = str(sid)
            ET.SubElement(ps, "SettingValue").text = str(new_val)
            ET.SubElement(ps, "ValueType").text = "Dword"

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
            creationflags=CREATE_NO_WINDOW,
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
        gpu_generation: Deprecated/ignored; the DLSS preset is now resolved from
            GPU capability + config.nvidia.dlss.priority via get_preset.
        pre_backup_path: Path to an already-created backup .nip. If provided,
            the internal backup step is skipped (avoids duplicate exports).

    Returns True on success.
    """
    npi_exe = find_npi_exe()
    if npi_exe is None:
        raise FileNotFoundError("NVIDIA Profile Inspector binary not found")

    if pre_backup_path is not None:
        backup_path = pre_backup_path
    else:
        backup_path = backup_nvidia_profile(npi_exe)
        action_logger.log_action("NPI Fix", "Backup created", backup_path)

    with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmpdir:
        source_nip, _ = export_current_profile(npi_exe, tmpdir)

        target: dict[int, int] = {}

        # G-Sync
        if config.nvidia.profile.gsync:
            for key in [
                "gsync_global_feature", "gsync_global_mode", "gsync_app_mode",
                "gsync_app_state", "gsync_app_requested",
                "gsync_indicator_overlay", "gsync_support_indicator",
            ]:
                target[SETTING_IDS[key]] = TARGET_VALUES[key]
        else:
            target[SETTING_IDS["gsync_global_feature"]] = 0

        # VSync
        _VSYNC_RAW = {"force_on": 0x47814940, "off": 0}
        if config.nvidia.profile.vsync == "force_on":
            for key in ["vsync", "vsync_tear_control", "vsync_smooth_afr"]:
                target[SETTING_IDS[key]] = TARGET_VALUES[key]
        else:
            target[SETTING_IDS["vsync"]] = _VSYNC_RAW.get(config.nvidia.profile.vsync, 0)

        # FPS cap
        if refresh_hz is None:
            refresh_hz = _get_primary_refresh_hz(specs)
        cap: int | None = None
        fps_override = config.nvidia.profile.fps_cap_override
        if fps_override is not None:
            cap = fps_override
            target[SETTING_IDS["fps_limiter_v3"]] = cap
            action_logger.log_action("NPI Fix", f"FPS cap: {cap}", "config override")
        elif refresh_hz and refresh_hz > 0:
            cap = calculate_fps_cap(refresh_hz)
            target[SETTING_IDS["fps_limiter_v3"]] = cap
            action_logger.log_action("NPI Fix", f"FPS cap: {cap}", f"{refresh_hz}Hz monitor")

        nvidia = specs.get("NVIDIA", [])
        bios_rebar = nvidia[0].get("ReBAR") if isinstance(nvidia, list) and nvidia else None
        if bios_rebar is True:
            target[SETTING_IDS["rebar_enable"]] = TARGET_VALUES["rebar_enable"]

        gpu_name = nvidia[0].get("GPU", "") if isinstance(nvidia, list) and nvidia else ""
        preset = get_preset(gpu_name, config.nvidia.dlss.priority)
        if preset is not None:
            target[SETTING_IDS["dlss_preset_profile"]] = TARGET_VALUES["dlss_preset_profile"]
            target[SETTING_IDS["dlss_preset_letter"]] = preset.value

        # Power management
        _POWER_RAW = {"max_performance": 1, "adaptive": 0}
        target[SETTING_IDS["power_mgmt"]] = _POWER_RAW.get(config.nvidia.profile.power_mgmt, 1)

        modified_nip = build_optimized_nip(source_nip, target)

    try:
        ok, msg = apply_nvidia_profile(npi_exe, modified_nip)
    finally:
        try:
            os.unlink(modified_nip)
        except OSError:
            pass

    if ok:
        changes = []
        if cap is not None:
            changes.append(f"FPS cap={cap}")
        if preset is not None:
            changes.append(f"DLSS={preset.letter}")
        if bios_rebar is True:
            changes.append("ReBar=ON")
        changes.append("G-Sync=ON" if config.nvidia.profile.gsync else "G-Sync=OFF")
        changes.append(f"VSync={config.nvidia.profile.vsync}")
        changes.append(f"PowerMgmt={config.nvidia.profile.power_mgmt}")
        action_logger.log_action("NPI Fix", "Applied", ", ".join(changes))
        return True

    action_logger.log_action("NPI Fix", "FAILED", msg)
    raise SetterError(f"Profile import failed -- original profile preserved at {backup_path}. Error: {msg}")


def fix_nvidia_dlss_preset(
    specs: dict,
    gpu_generation: str | None = None,
    pre_backup_path: str | None = None,
) -> bool:
    """Apply ONLY the per-GPU DLSS preset (Forced Model Preset = Custom + letter).

    Mirrors ``fix_nvidia_profile`` but writes just the two DLSS SettingIDs,
    leaving every other driver-profile setting untouched. The preset letter is
    resolved from GPU capability + ``config.nvidia.dlss.priority`` via
    ``get_preset``.

    Args:
        specs: Full system specs dict.
        gpu_generation: Deprecated/ignored; retained for signature compatibility.
        pre_backup_path: Path to an already-created backup .nip. If provided,
            the internal backup step is skipped (avoids duplicate exports).

    Returns True on success.

    Raises:
        FileNotFoundError: NPI binary not found.
        SetterError: GPU is not DLSS-capable, or import failed.
    """
    npi_exe = find_npi_exe()
    if npi_exe is None:
        raise FileNotFoundError("NVIDIA Profile Inspector binary not found")

    nvidia = specs.get("NVIDIA", [])
    gpu_name = nvidia[0].get("GPU", "") if isinstance(nvidia, list) and nvidia else ""
    preset = get_preset(gpu_name, config.nvidia.dlss.priority)
    if preset is None:
        raise SetterError(f"No DLSS preset for GPU: {gpu_name!r}")

    if pre_backup_path is not None:
        backup_path = pre_backup_path
    else:
        backup_path = backup_nvidia_profile(npi_exe)
        action_logger.log_action("NPI DLSS Fix", "Backup created", backup_path)

    with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmpdir:
        source_nip, _ = export_current_profile(npi_exe, tmpdir)

        target: dict[int, int] = {
            SETTING_IDS["dlss_preset_profile"]: TARGET_VALUES["dlss_preset_profile"],
            SETTING_IDS["dlss_preset_letter"]: preset.value,
        }

        modified_nip = build_optimized_nip(source_nip, target)

    try:
        ok, msg = apply_nvidia_profile(npi_exe, modified_nip)
    finally:
        try:
            os.unlink(modified_nip)
        except OSError:
            pass

    if ok:
        action_logger.log_action("NPI DLSS Fix", "Applied", f"DLSS={preset.letter} ({preset.priority})")
        return True

    action_logger.log_action("NPI DLSS Fix", "FAILED", msg)
    raise SetterError(
        f"DLSS preset import failed -- original profile preserved at {backup_path}. Error: {msg}"
    )
