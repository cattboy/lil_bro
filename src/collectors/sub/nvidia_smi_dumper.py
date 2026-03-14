import subprocess
import re
import xml.etree.ElementTree as ET

def get_nvidia_smi() -> list | str:
    try:
        result = subprocess.run([
            "nvidia-smi",
            "-x",
            "-q"
        ], capture_output=True, text=True)
        root = ET.fromstring(result.stdout)

        # Driver lives at root level, outside <gpu>
        drv = root.findtext("driver_version")
        rows = []
        for gpu in root.findall("gpu"):
            n                = gpu.findtext("product_name")
            bar1_raw         = gpu.findtext("bar1_memory_usage/used")
            pcie_max_raw     = gpu.findtext("pci/pci_gpu_link_info/link_widths/max_link_width")
            pcie_current_raw = gpu.findtext("pci/pci_gpu_link_info/link_widths/current_link_width")

            bar1_used    = int(re.search(r"\d+", bar1_raw).group())         if bar1_raw         else 0
            pcie_max     = int(re.search(r"\d+", pcie_max_raw).group())     if pcie_max_raw     else None
            pcie_current = int(re.search(r"\d+", pcie_current_raw).group()) if pcie_current_raw else None

            rebar = True if bar1_used > 256 else False

            rows.append({
                "GPU":                n,
                "Driver":             drv,
                "BAR1 Used (MiB)":    bar1_used,
                "PCIe Max Width":     pcie_max,
                "PCIe Current Width": pcie_current,
                "ReBAR":              rebar,
            })
        return rows
    except FileNotFoundError:
        return "nvidia-smi not found"
    except Exception as e:
        return f"nvidia-smi error: {e}"