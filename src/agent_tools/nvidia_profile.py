"""
NVIDIA Profile Inspector analyzer.

Checks driver-level settings (G-Sync, VSync, FPS cap, ReBar driver toggle,
DLSS preset, power management) against gaming best practices. Returns a single
finding dict — all settings are fixed atomically via one .nip import.
"""

import re
from typing import Any

from ..collectors.sub.nvidia_profile_dumper import SETTING_IDS, TARGET_VALUES, DLSS_LETTER_MAP


def calculate_fps_cap(refresh_hz: int) -> int:
    """Blur Busters formula: cap = round(refresh_hz - refresh_hz^2 / 4096).

    Produces 226 for 240Hz, 328 for 360Hz, 424 for 480Hz.
    """
    return round(refresh_hz - (refresh_hz * refresh_hz / 4096))


# GPU generation → recommended DLSS preset letter + hex value
DLSS_PRESETS: dict[str, tuple[str, int]] = {
    "50": ("L", 0x0C),   # RTX 50-series — Transformer Gen 2
    "40": ("L", 0x0C),   # RTX 40-series — Transformer Gen 2
    "30": ("K", 0x0B),   # RTX 30-series — Transformer Gen 1
    "20": ("K", 0x0B),   # RTX 20-series — Transformer Gen 1
}


def _get_gpu_generation(gpu_name: str) -> str | None:
    """Extract RTX generation from GPU name (e.g. 'NVIDIA GeForce RTX 4090' → '40')."""
    m = re.search(r"RTX\s*(\d)0", gpu_name, re.IGNORECASE)
    if m:
        return m.group(1) + "0"
    return None


def _get_primary_refresh_hz(specs: dict) -> int | None:
    """Extract primary monitor refresh rate from specs."""
    displays = specs.get("DisplayCapabilities", [])
    if not displays:
        return None
    primary = displays[0]
    max_hz = primary.get("max_refresh_hz", 0)
    edid_max = primary.get("edid_declared_max_hz") or 0
    current = primary.get("current_refresh_hz", 0)
    best = max(max_hz, edid_max, current)
    return best if best > 0 else None


def _check_gsync(npi: dict, raw: dict[int, int]) -> dict[str, Any]:
    """Check all 7 G-Sync settings."""
    gsync_keys = [
        "gsync_global_feature", "gsync_global_mode", "gsync_app_mode",
        "gsync_app_state", "gsync_app_requested",
        "gsync_indicator_overlay", "gsync_support_indicator",
    ]
    mismatches = []
    for key in gsync_keys:
        sid = SETTING_IDS[key]
        current = raw.get(sid)
        expected = TARGET_VALUES[key]
        if current != expected:
            mismatches.append(key)

    if not mismatches:
        return {"name": "G-Sync", "ok": True, "message": "G-Sync fully configured"}
    return {
        "name": "G-Sync",
        "ok": False,
        "message": f"G-Sync not optimized ({len(mismatches)} settings need adjustment)",
        "mismatches": mismatches,
    }


def _check_vsync(npi: dict, raw: dict[int, int]) -> dict[str, Any]:
    """Check VSync force-on + tear control + smooth AFR."""
    vsync_keys = ["vsync", "vsync_tear_control", "vsync_smooth_afr"]
    mismatches = []
    for key in vsync_keys:
        sid = SETTING_IDS[key]
        current = raw.get(sid)
        expected = TARGET_VALUES[key]
        if current != expected:
            mismatches.append(key)

    if not mismatches:
        return {"name": "VSync", "ok": True, "message": "VSync correctly forced on"}
    return {
        "name": "VSync",
        "ok": False,
        "message": f"VSync not configured for Blur Busters optimal ({len(mismatches)} settings)",
        "mismatches": mismatches,
    }


def _check_fps_cap(npi: dict, raw: dict[int, int], refresh_hz: int | None) -> dict[str, Any]:
    """Check frame rate limiter against formula-calculated cap."""
    if refresh_hz is None:
        return {
            "name": "FPS Cap",
            "ok": True,
            "message": "Could not determine monitor refresh rate — FPS cap not checked",
            "skipped": True,
        }

    expected_cap = calculate_fps_cap(refresh_hz)
    current_cap = raw.get(SETTING_IDS["fps_limiter_v3"])

    if current_cap == expected_cap:
        return {
            "name": "FPS Cap",
            "ok": True,
            "message": f"FPS cap correctly set to {expected_cap} for {refresh_hz}Hz monitor",
        }
    current_str = str(current_cap) if current_cap is not None else "not set"
    return {
        "name": "FPS Cap",
        "ok": False,
        "message": f"FPS cap is {current_str}, should be {expected_cap} for {refresh_hz}Hz monitor",
        "current": current_cap,
        "expected": expected_cap,
    }


def _check_rebar_driver(npi: dict, raw: dict[int, int], bios_rebar: bool | None) -> dict[str, Any]:
    """Check driver-side ReBar toggle (only relevant if BIOS ReBar is ON)."""
    if bios_rebar is not True:
        return {
            "name": "ReBar Driver",
            "ok": True,
            "message": "BIOS-level ReBar not enabled — driver toggle not applicable",
            "skipped": True,
        }

    current = raw.get(SETTING_IDS["rebar_enable"])
    if current == 1:
        return {"name": "ReBar Driver", "ok": True, "message": "Driver-side ReBar enabled"}
    return {
        "name": "ReBar Driver",
        "ok": False,
        "message": "Driver-side ReBar toggle is disabled (BIOS ReBar is ON)",
        "current": current,
        "expected": 1,
    }


def _check_dlss(npi: dict, raw: dict[int, int], gpu_name: str) -> dict[str, Any]:
    """Check DLSS preset against GPU generation recommendation."""
    gen = _get_gpu_generation(gpu_name)
    if gen is None:
        return {
            "name": "DLSS Preset",
            "ok": True,
            "message": "Could not detect RTX generation — DLSS preset not checked",
            "skipped": True,
        }

    preset_info = DLSS_PRESETS.get(gen)
    if preset_info is None:
        return {
            "name": "DLSS Preset",
            "ok": True,
            "message": f"No DLSS preset recommendation for generation {gen}",
            "skipped": True,
        }

    expected_letter, expected_hex = preset_info

    # Check both the profile mode (must be Custom=2) and the preset letter
    profile_val = raw.get(SETTING_IDS["dlss_preset_profile"])
    letter_val = raw.get(SETTING_IDS["dlss_preset_letter"])
    current_letter = DLSS_LETTER_MAP.get(letter_val, "unknown") if letter_val is not None else "not set"

    if profile_val == 2 and letter_val == expected_hex:
        return {
            "name": "DLSS Preset",
            "ok": True,
            "message": f"DLSS Preset {expected_letter} correctly set for RTX {gen}-series",
        }
    return {
        "name": "DLSS Preset",
        "ok": False,
        "message": f"DLSS preset is '{current_letter}', recommended Preset {expected_letter} for RTX {gen}-series",
        "current_letter": current_letter,
        "expected_letter": expected_letter,
    }


def _check_power_mgmt(npi: dict, raw: dict[int, int]) -> dict[str, Any]:
    """Check power management mode."""
    current = raw.get(SETTING_IDS["power_mgmt"])
    if current == TARGET_VALUES["power_mgmt"]:
        return {"name": "Power Management", "ok": True, "message": "Prefer Maximum Performance is set"}
    current_str = npi.get("power_mgmt") or ("not set" if current is None else f"value {current}")
    return {
        "name": "Power Management",
        "ok": False,
        "message": f"Power management is '{current_str}', should be 'Prefer Maximum Performance'",
        "current": current,
        "expected": TARGET_VALUES["power_mgmt"],
    }


def analyze_nvidia_profile(specs: dict) -> dict[str, Any]:
    """Analyze NVIDIA driver profile settings against gaming best practices.

    Returns a single finding dict. All sub-checks are bundled because they're
    fixed atomically via one .nip import operation.
    """
    nvidia = specs.get("NVIDIA", "")

    # AMD guard — skip if no NVIDIA GPU
    if not (isinstance(nvidia, list) and nvidia):
        amd = specs.get("AMD", "")
        if isinstance(amd, list) and amd:
            return {
                "check": "nvidia_profile",
                "status": "SKIPPED",
                "message": "AMD GPU detected — NVIDIA profile optimization not applicable.",
                "can_auto_fix": False,
            }
        return {
            "check": "nvidia_profile",
            "status": "SKIPPED",
            "message": "No NVIDIA GPU detected — NPI features require an NVIDIA GPU.",
            "can_auto_fix": False,
        }

    gpu_info = nvidia[0]
    gpu_name = gpu_info.get("GPU", "Unknown GPU")
    bios_rebar = gpu_info.get("ReBAR")

    npi = specs.get("NVIDIAProfile", {})
    if not npi.get("available"):
        reason = npi.get("reason") or npi.get("error") or "unknown"
        return {
            "check": "nvidia_profile",
            "status": "UNKNOWN",
            "message": f"NVIDIA Profile Inspector unavailable: {reason}",
            "can_auto_fix": False,
        }

    if "error" in npi:
        return {
            "check": "nvidia_profile",
            "status": "UNKNOWN",
            "message": f"Could not read NVIDIA profile: {npi['error']}",
            "can_auto_fix": False,
        }

    raw_settings = npi.get("raw_settings", {})
    refresh_hz = _get_primary_refresh_hz(specs)

    # Run all sub-checks
    sub_findings = [
        _check_gsync(npi, raw_settings, ),
        _check_vsync(npi, raw_settings),
        _check_fps_cap(npi, raw_settings, refresh_hz),
        _check_rebar_driver(npi, raw_settings, bios_rebar),
        _check_dlss(npi, raw_settings, gpu_name),
        _check_power_mgmt(npi, raw_settings),
    ]

    failed = [s for s in sub_findings if not s["ok"]]
    all_ok = len(failed) == 0

    if all_ok:
        return {
            "check": "nvidia_profile",
            "status": "OK",
            "message": "NVIDIA driver profile is fully optimized.",
            "can_auto_fix": False,
            "sub_findings": sub_findings,
        }

    # Build summary of what's wrong
    names = [f["name"] for f in failed]
    summary = ", ".join(names)

    # Build current/expected for the finding
    expected_fps = calculate_fps_cap(refresh_hz) if refresh_hz else None
    gpu_gen = _get_gpu_generation(gpu_name)
    dlss_info = DLSS_PRESETS.get(gpu_gen) if gpu_gen else None

    return {
        "check": "nvidia_profile",
        "status": "WARNING",
        "current": {
            "gpu_model": gpu_name,
            "gsync": npi.get("gsync_enabled"),
            "vsync": npi.get("vsync_mode"),
            "fps_cap": npi.get("fps_cap"),
            "rebar_driver": npi.get("rebar_driver"),
            "dlss_preset": npi.get("dlss_preset"),
            "power_mgmt": npi.get("power_mgmt"),
        },
        "expected": {
            "gsync": True,
            "vsync": "force_on",
            "fps_cap": expected_fps,
            "rebar_driver": True if bios_rebar else None,
            "dlss_preset": dlss_info[0] if dlss_info else None,
            "power_mgmt": "max_performance",
        },
        "message": f"NVIDIA driver profile not optimized: {summary}",
        "can_auto_fix": True,
        "sub_findings": sub_findings,
    }
