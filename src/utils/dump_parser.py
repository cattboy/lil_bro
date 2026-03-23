"""
dump_parser.py — Extracts a slim hardware summary from full_specs.json.

Produces the "hardware" portion of the LLM input dict:
  {
    "cpu":        "Intel Core i9-13900K (24 cores, 5600 MHz)",
    "gpu":        "NVIDIA GeForce RTX 4090 (24576 MB VRAM)",
    "gpu_driver": "546.33",
    "ram_gb":     64.0,
    "ram_mhz":    6000,
    "os":         "Windows 11 Pro 10.0.22631",
    "motherboard": "ASUS ROG MAXIMUS Z790 HERO",
  }

This is intentionally narrow — only what the LLM needs to reason about
hardware context. Full raw data stays in full_specs.json.
"""

from __future__ import annotations
import json
from pathlib import Path


def extract_hardware_summary(specs: dict) -> dict:
    """
    Takes the raw full_specs dict (as loaded from full_specs.json) and returns
    a slim hardware summary dict suitable for LLM context injection.
    """
    wmi = specs.get("WMI", {})
    nvidia = specs.get("NVIDIA", [])

    # CPU
    cpu_list = wmi.get("CPU", [])
    if cpu_list:
        c = cpu_list[0]
        cpu = f"{c.get('Name', 'Unknown CPU')} ({c.get('Cores', '?')} cores, {c.get('Speed_MHz', '?')} MHz)"
    else:
        cpu = "Unknown"

    # GPU — prefer nvidia-smi data, fall back to WMI VideoController
    gpu = "Unknown"
    gpu_driver = "Unknown"
    if isinstance(nvidia, list) and nvidia:
        g = nvidia[0]
        gpu = g.get("GPU", "Unknown GPU")
        gpu_driver = g.get("Driver", "Unknown")
    else:
        vc_list = wmi.get("VideoController", [])
        if vc_list:
            gpu = vc_list[0].get("Name", "Unknown GPU")

    # RAM
    ram_list = wmi.get("RAM", [])
    ram_gb = round(sum(m.get("Capacity_GB", 0) for m in ram_list), 1)
    ram_mhz = 0
    if ram_list:
        m = ram_list[0]
        ram_mhz = int(m.get("Configured_MHz", 0) or m.get("Speed_MHz", 0) or 0)

    # OS
    os_list = wmi.get("OS", [])
    os_str = os_list[0].get("Name", "Unknown OS") if os_list else "Unknown"

    # Motherboard
    mb_list = wmi.get("Motherboard", [])
    if mb_list:
        mb = f"{mb_list[0].get('Make', '')} {mb_list[0].get('Model', '')}".strip()
    else:
        mb = "Unknown"

    return {
        "cpu":         cpu,
        "gpu":         gpu,
        "gpu_driver":  gpu_driver,
        "ram_gb":      ram_gb,
        "ram_mhz":     ram_mhz,
        "os":          os_str,
        "motherboard": mb,
    }


def load_and_parse(specs_path: str | Path) -> dict:
    """
    Loads full_specs.json from disk and returns the slim hardware summary.
    Returns an empty dict if the file cannot be read.
    """
    try:
        with open(specs_path, "r", encoding="utf-8") as f:
            specs = json.load(f)
        return extract_hardware_summary(specs)
    except Exception:
        return {}


if __name__ == "__main__":
    from .paths import get_specs_path
    default = get_specs_path()
    summary = load_and_parse(default)
    print(json.dumps(summary, indent=2))
