import subprocess
import xml.etree.ElementTree as ET
from typing import Any

def get_nvidia_smi() -> list[dict[str, Any]]:
    """
    Executes nvidia-smi and parses the XML output from memory.
    
    Raises:
        FileNotFoundError: If nvidia-smi is not installed/in PATH.
        RuntimeError: If the subprocess fails or XML parsing fails.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "-x", "-q"], 
            capture_output=True, 
            text=True, 
            check=True
        )
    except FileNotFoundError as e:
        raise FileNotFoundError("nvidia-smi executable not found in PATH.") from e
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"nvidia-smi execution failed: {e.stderr}") from e

    root = ET.fromstring(result.stdout)
    driver_version = root.findtext("driver_version")
    
    rows =[]
    for gpu in root.findall("gpu"):
        bar1_raw = gpu.findtext("bar1_memory_usage/used")
        pcie_max_raw = gpu.findtext("pci/pci_gpu_link_info/link_widths/max_link_width")
        pcie_current_raw = gpu.findtext("pci/pci_gpu_link_info/link_widths/current_link_width")

        # Extract digits efficiently, defaulting to None/0 if missing
        bar1_used = int(''.join(filter(str.isdigit, bar1_raw))) if bar1_raw else 0
        pcie_max = int(''.join(filter(str.isdigit, pcie_max_raw))) if pcie_max_raw else None
        pcie_current = int(''.join(filter(str.isdigit, pcie_current_raw))) if pcie_current_raw else None

        rows.append({
            "GPU":                gpu.findtext("product_name"),
            "Driver":             driver_version,
            "BAR1 Used (MiB)":    bar1_used,
            "PCIe Max Width":     pcie_max,
            "PCIe Current Width": pcie_current,
            "ReBAR":              bool(bar1_used > 256),
        })
        
    return rows