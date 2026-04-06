import json
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
from ..utils.formatting import print_step, print_step_done, print_error, print_warning
from ..utils.paths import get_specs_path


def _safe_collect(fn, *args, **kwargs):
    """Wraps a collector call so a single failure doesn't abort the whole dump."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
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


def dump_system_specs(output_path: str | None = None) -> str:
    """
    Consolidates data from all hardware tools into a single JSON file.
    Defaults to <project_root>/logs/full_specs.json.
    """
    if output_path is None:
        output_path = str(get_specs_path())

    print_step("Collecting Unified System Specifications")

    specs = {
        "CollectionTime": datetime.now().isoformat(),
        "WMI": _safe_collect(get_wmi_specs),
        "DXDiag": _safe_collect(get_dxdiag),
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
        print_step_done(True)
        return output_path
    except Exception as e:
        print_step_done(False)
        print_error(f"Failed to save {output_path}: {e}")
        return ""

if __name__ == "__main__":
    out = dump_system_specs()
    if out:
        print(f"Saved specs to {out}")
