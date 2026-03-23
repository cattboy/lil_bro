from pathlib import Path
from .sub.amd_smi_dumper import get_amd_smi
from .sub.dxdiag_dumper import get_dxdiag
from .sub.libra_hm_dumper import get_lhm_data
from .sub.monitor_dumper import get_monitor_refresh_capabilities
from .sub.nvidia_smi_dumper import get_nvidia_smi
from .sub.wmi_dumper import get_wmi_specs
from ..agent_tools.power_plan import get_active_power_plan
from ..agent_tools.game_mode import get_game_mode_status
from ..agent_tools.temp_audit import get_temp_sizes
import json
from datetime import datetime
from ..utils.formatting import print_step, print_step_done, print_error, print_warning

# Stable output path: <project_root>/logs/full_specs.json
_DEFAULT_OUTPUT = Path(__file__).parent.parent.parent / "logs" / "full_specs.json"


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
        output_path = str(_DEFAULT_OUTPUT)
        _DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    print_step("Collecting Unified System Specifications")

    specs = {
        "CollectionTime": datetime.now().isoformat(),
        "WMI": get_wmi_specs(),
        "DXDiag": get_dxdiag(),
        "NVIDIA": get_nvidia_smi(),
        "AMD": get_amd_smi(),
        "LibreHardwareMonitor": get_lhm_data(),
        "DisplayCapabilities": get_monitor_refresh_capabilities(),
        "PowerPlan": _collect_power_plan(),
        "GameMode": _collect_game_mode(),
        "TempFolders": get_temp_sizes(),
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
