import platform
import time
import os
import subprocess
import xml.etree.ElementTree as ET

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