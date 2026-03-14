from logging import root
import platform
import subprocess
import time
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime
try:
    import wmi
except ImportError:
    wmi = None

from ..utils.formatting import print_step, print_step_done, print_error, print_warning

def get_wmi_specs() -> dict:
    if wmi is None:
        return {"error": "WMI module not installed or unsupported OS"}
    try:
        c = wmi.WMI()
        return {
            "OS": [{"Name": o.Caption, "Version": o.Version} for o in c.Win32_OperatingSystem()],
            "CPU": [{"Name": p.Name, "Cores": p.NumberOfCores, "Speed_MHz": p.MaxClockSpeed} for p in c.Win32_Processor()],
            "RAM": [{"Capacity_GB": round(int(r.Capacity)/1e9, 1), "Speed_MHz": r.Speed, "Configured_MHz": getattr(r, 'ConfiguredClockSpeed', 0)} for r in c.Win32_PhysicalMemory()],
            "Motherboard": [{"Make": m.Manufacturer, "Model": m.Product} for m in c.Win32_BaseBoard()],
            "BIOS": [{"Version": b.SMBIOSBIOSVersion} for b in c.Win32_BIOS()],
            "VideoController": [{"Name": v.Name, "VRAM_MB": int(getattr(v, 'AdapterRAM', 0) or 0) / (1024*1024), "RefreshRate": getattr(v, 'CurrentRefreshRate', 0)} for v in c.Win32_VideoController()],
            "DiskDrive": [{"Model": d.Model, "Size_GB": round(int(d.Size or 0)/1e9, 1)} for d in c.Win32_DiskDrive()]
        }
    except Exception as e:
        return {"error": f"WMI query failed: {e}"}

def get_dxdiag(output_path: str = "C:\\Temp\\dxdiag.xml") -> dict:
    if platform.system() != "Windows":
        return {"error": "DXDiag only supported on Windows"}
        
    try:
        # Ensure temp directory exists
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Run dxdiag silently
        subprocess.run(["dxdiag", "/x", output_path], check=False)
        
        # DxDiag takes a bit of time to generate the file asynchronously
        for _ in range(15):
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                break
            time.sleep(1)
            
        tree = ET.parse(output_path)
        root = tree.getroot()
        
        return {
            "DirectXVersion": root.findtext(".//DirectXVersion"),
            "DisplayDevices": [{c.tag: c.text for c in d if c.text} for d in root.findall(".//DisplayDevice")],
            "SoundDevices": [{c.tag: c.text for c in d if c.text} for d in root.findall(".//SoundDevice")],
            "LogicalDisks": [{c.tag: c.text for c in d if c.text} for d in root.findall(".//LogicalDisk")]
        }
    except Exception as e:
        return {"error": f"Failed to parse DXDiag: {e}"}
    finally:
        # Cleanup
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass

def get_nvidia_smi() -> list | str:
    try:
        result = subprocess.run([
            "nvidia-smi",
            "-x",
            "-q"
        ], capture_output=True, text=True)

        root = ET.fromstring(result.stdout)
        rows = []
        for gpu in root.findall("gpu"):
            n = gpu.findtext("product_name")
            drv = gpu.findtext("driver_version")
            bar1_used = gpu.findtext("bar1_memory_usage/used")
            pcie_max = gpu.findtext("pci/link_widths/max_link_width")
            pcie_current = gpu.findtext("pci/link_widths/current_link_width")
            # If BAR1 is extremely large (> 256MB usually), ReBAR is likely enabled
            rebar_enabled = "Enabled" if bar1_used.isdigit() and int(bar1_used) > 256 else "Disabled"
            
            rows.append({
                "GPU": n,
                "Driver": drv, 
                "BAR1 Used MiB": bar1_used,
                "Link Width Max": pcie_max, 
                "Link Width Current": pcie_current, 
                "ReBAR": rebar_enabled
                })
        return rows
    except FileNotFoundError:
        return "nvidia-smi not found"
    except Exception as e:
        return f"nvidia-smi error: {e}"

def get_amd_smi() -> list | str:
    """Attempts to use the amdsmi Python library (Linux/WSL) or amd-smi CLI."""
    try:
        import amdsmi
        try:
            amdsmi.amdsmi_init()
            devices = amdsmi.amdsmi_get_processor_handles()
            rows = []
            for device in devices:
                # Basic board info
                try:
                    board_info = amdsmi.amdsmi_get_gpu_board_info(device)
                    name = board_info.get("product_name", "Unknown AMD GPU")
                except:
                    name = "Unknown AMD GPU"
                
                # VRAM
                try:
                    vram_info = amdsmi.amdsmi_get_gpu_vram_info(device)
                    vram_mb = int(vram_info.get("vram_size", 0))
                except:
                    vram_mb = 0
                
                # Driver
                try:
                    driver_info = amdsmi.amdsmi_get_gpu_driver_info(device)
                    driver = driver_info.get("driver_version", "Unknown")
                except:
                    driver = "Unknown"
                
                rows.append({
                    "GPU": name,
                    "VRAM_MiB": vram_mb,
                    "Driver": driver,
                    # Note: direct ReBAR query not broadly supported in Windows consumer amdsmi yet
                    "ReBAR": "Unknown via amdsmi" 
                })
                
            amdsmi.amdsmi_shut_down()
            return rows if rows else "No AMD GPUs found via amdsmi"
        except Exception as e:
             return f"amdsmi library exception: {e}"
             
    except ImportError:
        # Fallback to CLI if possible
        try:
           result = subprocess.run(["amd-smi", "static"], capture_output=True, text=True)
           if result.returncode == 0:
               return "amd-smi CLI found but requires parsing implementation"
           return "amdsmi Python module not installed and CLI failed"
        except FileNotFoundError:
           return "amdsmi Python module not installed and CLI not found"

def get_lhm_data() -> dict | str:
    """
    Placeholder for LibreHardwareMonitor integration.
    If LHM exposes a web server or JSON dump, fetch it here.
    """
    import urllib.request
    try:
        # If LHM is running with Remote Web Server enabled
        req = urllib.request.Request("http://localhost:8085/data.json")
        with urllib.request.urlopen(req, timeout=2) as response:
            return json.loads(response.read())
    except Exception as e:
        return f"LibreHardwareMonitor not reachable at localhost:8085 ({e})"

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
        "LibreHardwareMonitor": get_lhm_data()
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
