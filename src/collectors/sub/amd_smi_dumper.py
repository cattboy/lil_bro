import subprocess
# Currently not working, need AMD GPU to test and develop against. Placeholder for future AMD support via amdsmi library or CLI parsing.
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