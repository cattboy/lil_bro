from logging import root
from .sub.amd_smi_dumper import get_amd_smi
from .sub.dxdiag_dumper import get_dxdiag
from .sub.libra_hm_dumper import get_lhm_data
from .sub.monitor_dumper import get_monitor_refresh_capabilities
from .sub.nvidia_smi_dumper import get_nvidia_smi
from .sub.wmi_dumper import get_wmi_specs
import json
from datetime import datetime
from ..utils.formatting import print_step, print_step_done, print_error, print_warning

def dump_system_specs(output_path: str = "full_specs.json") -> str:
    """
    Consolidates data from all specific hardware tools into a single JSON file.
    """
    print_step("Collecting Unified System Specifications")
    
    specs = {
        "CollectionTime": datetime.now().isoformat(),
        "WMI": get_wmi_specs(),
        "DXDiag": get_dxdiag(),
        "NVIDIA": get_nvidia_smi(),
        "AMD": get_amd_smi(),
        "LibreHardwareMonitor": get_lhm_data(),
        "DisplayCapabilities": get_monitor_refresh_capabilities()
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
