import json
import os
from datetime import datetime

from .sub.amd_smi_dumper import get_amd_smi
from .sub.dxdiag_dumper import get_dxdiag
from .sub.libra_hm_dumper import get_lhm_data
from .sub.monitor_dumper import get_monitor_refresh_capabilities
from .sub.nvidia_profile_dumper import get_nvidia_profile
from .sub.nvidia_smi_dumper import get_nvidia_smi
from .sub.wmi_dumper import get_wmi_specs
from ..agent_tools.power_plan import get_active_power_plan
from ..agent_tools.game_mode import get_game_mode_status
from ..agent_tools.temp_audit import get_temp_sizes
from ..utils.formatting import print_step, print_step_done, print_error
from ..utils.paths import get_specs_path
from ..utils.debug_logger import get_debug_logger


def _safe_collect(fn, *args, **kwargs):
    """Wraps a collector call so a single failure doesn't abort the whole dump."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        get_debug_logger().warning("Collector %s failed: %s", getattr(fn, "__name__", repr(fn)), e)
        return {"error": str(e)}


def _collect_power_plan() -> dict:
    try:
        guid, name = get_active_power_plan()
        return {"guid": guid, "name": name}
    except Exception as e:
        return {"error": str(e)}


def _collect_game_mode() -> dict:
    try:
        return {"enabled": get_game_mode_status()}
    except Exception as e:
        return {"error": str(e)}


def collect_fix_sections(sections: set[str] | None = None) -> dict:
    """Re-collect the dashboard fix-relevant spec sections (optionally scoped).

    Same collectors as ``dump_system_specs``, narrowed to the sections the
    Dashboard fix cards consume (display, NVIDIA profile/DLSS, power plan, game
    mode). Lets the GUI refresh those cards live after an apply (pipeline / card
    fix / revert) without a full system dump -- the single source of truth shared
    with the optimization flow.

    ``sections`` scopes the work to just the requested keys (e.g. ``{"PowerPlan"}``)
    so a refresh only re-runs the collectors for whatever actually changed this
    session; ``None`` collects everything. The slow NVIDIA profile export is
    skipped unless an NVIDIA GPU is actually present (and only run when the
    ``NVIDIA``/``NVIDIAProfile`` keys are in scope).
    """
    def _want(key: str) -> bool:
        return sections is None or key in sections

    out: dict = {}
    if _want("DisplayCapabilities"):
        out["DisplayCapabilities"] = _safe_collect(get_monitor_refresh_capabilities)
    if _want("NVIDIA") or _want("NVIDIAProfile"):
        nvidia = _safe_collect(get_nvidia_smi)
        if _want("NVIDIA"):
            out["NVIDIA"] = nvidia
        if _want("NVIDIAProfile") and isinstance(nvidia, list) and nvidia:
            out["NVIDIAProfile"] = _safe_collect(get_nvidia_profile)
    if _want("PowerPlan"):
        out["PowerPlan"] = _collect_power_plan()
    if _want("GameMode"):
        out["GameMode"] = _collect_game_mode()
    return out


def dump_system_specs(output_path: str | None = None) -> str:
    """
    Consolidates data from all hardware tools into a single JSON file.
    Defaults to ./lil_bro/full_specs.json.
    """
    if output_path is None:
        output_path = str(get_specs_path())

    print_step("Collecting Unified System Specifications")

    specs = {
        "CollectionTime": datetime.now().isoformat(),
        "WMI": _safe_collect(get_wmi_specs),
        #"DXDiag": _safe_collect(get_dxdiag), # Commented out for time being, todo add later when need DXDIAG data
        "NVIDIA": _safe_collect(get_nvidia_smi),
        "AMD": _safe_collect(get_amd_smi),
        "LibreHardwareMonitor": _safe_collect(get_lhm_data),
        "DisplayCapabilities": _safe_collect(get_monitor_refresh_capabilities),
        "PowerPlan": _collect_power_plan(),
        "GameMode": _collect_game_mode(),
        "TempFolders": _safe_collect(get_temp_sizes),
        "NVIDIAProfile": _safe_collect(get_nvidia_profile),
    }

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(specs, f, indent=2, default=str)
        try:
            size_mb = os.path.getsize(output_path) / (1024 * 1024)
            if size_mb > 10:
                get_debug_logger().warning(
                    "full_specs.json is %.1f MB — unexpectedly large; check for collector anomaly",
                    size_mb,
                )
        except OSError:
            pass
        get_debug_logger().info("System specs saved to %s", output_path)
        print_step_done(True)
        return output_path
    except Exception as e:
        get_debug_logger().error("Failed to save specs to %s: %s", output_path, e)
        print_step_done(False)
        print_error(f"Failed to save {output_path}: {e}")
        return ""

if __name__ == "__main__":
    out = dump_system_specs()
    if out:
        print(f"Saved specs to {out}")
