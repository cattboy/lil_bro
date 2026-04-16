import subprocess, xml.etree.ElementTree as ET, re

if __name__ == "__main__":
    result = subprocess.run(["nvidia-smi", "-x", "-q"], capture_output=True, text=True)
    root = ET.fromstring(result.stdout)

    # Driver lives at root level, outside <gpu>
    drv = root.findtext("driver_version")
    cuda = root.findtext("cuda_version")

    rows = []
    for gpu in root.findall("gpu"):
        n                = gpu.findtext("product_name")
        bar1_raw         = gpu.findtext("bar1_memory_usage/used")
        pcie_max_raw     = gpu.findtext("pci/pci_gpu_link_info/link_widths/max_link_width")
        pcie_current_raw = gpu.findtext("pci/pci_gpu_link_info/link_widths/current_link_width")

        bar1_used    = int(re.search(r"\d+", bar1_raw).group())         if bar1_raw         else 0
        pcie_max     = int(re.search(r"\d+", pcie_max_raw).group())     if pcie_max_raw     else None
        pcie_current = int(re.search(r"\d+", pcie_current_raw).group()) if pcie_current_raw else None

        rebar = "Enabled" if bar1_used > 256 else "Disabled"

        rows.append({
            "GPU":                n,
            "Driver":             drv,
            "CUDA":               cuda,
            "BAR1 Used (MiB)":    bar1_used,
            "PCIe Max Width":     pcie_max,
            "PCIe Current Width": pcie_current,
            "ReBAR":              rebar,
        })

        print(f"{n} | Driver: {drv} | CUDA: {cuda} | BAR1: {bar1_used} MiB | ReBAR: {rebar} | PCIe: {pcie_current}x / {pcie_max}x")
