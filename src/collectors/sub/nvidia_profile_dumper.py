"""
NVIDIA Profile Inspector collector.

Exports the current NVIDIA driver profile via NPI CLI and parses
the .nip XML to extract key driver settings (G-Sync, VSync, FPS cap,
ReBar, DLSS preset, power management).
"""

import subprocess
import tempfile
import xml.etree.ElementTree as ET
from typing import Any

from ...utils.debug_logger import get_debug_logger
from ...utils.errors import NvapiInitError, SetterError
from ...utils.nvidia_npi import (
    DLSS_LETTER_MAP,
    SETTING_IDS,
    export_current_profile,
    find_npi_exe,
)
from ...utils.paths import get_temp_dir

log = get_debug_logger()


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
    return raw.get(SETTING_IDS["fps_limiter_v3"])


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
        log.info("NPI Collector: Skipped -- binary not found")
        return {"available": False, "reason": "NPI binary not found"}

    log.info("NPI Collector: Invoked %s", npi_exe)

    with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmpdir:
        try:
            _, raw_settings = export_current_profile(npi_exe, tmpdir)
        except subprocess.TimeoutExpired:
            log.warning("NPI Collector: Timeout -- export timed out after 30s")
            return {"available": True, "error": "NPI export timed out"}
        except FileNotFoundError:
            log.info("NPI Collector: Skipped -- binary not found at runtime")
            return {"available": False, "reason": "NPI binary not found"}
        except NvapiInitError:
            log.info("NPI Collector: Skipped -- no NVIDIA GPU detected -- NVAPI failed to initialize")
            return {"available": False, "reason": "No NVIDIA GPU detected"}
        except SetterError as e:
            msg = str(e)
            action = "NotReady" if "NPI .nip not ready after" in msg else "Failed"
            log.warning("NPI Collector: %s -- %s", action, msg)
            return {"available": True, "error": msg}
        except (ET.ParseError, UnicodeDecodeError, ValueError) as e:
            log.warning("NPI Collector: ParseError -- %s", e)
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