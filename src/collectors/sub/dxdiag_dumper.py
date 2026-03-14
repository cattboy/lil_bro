import platform
import time
import tempfile
import os
import subprocess
import xml.etree.ElementTree as ET
from typing import Any

def get_dxdiag() -> dict[str, Any]:
    """
    Executes DXDiag and parses the resulting XML hardware report.
    
    Raises:
        RuntimeError: If executed outside Windows or if the file fails to generate.
    """
    if platform.system() != "Windows":
        raise RuntimeError("DXDiag is only supported on Windows environments.")

    # Utilize a secure, self-cleaning temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_path = os.path.join(temp_dir, "dxdiag.xml")
        
        subprocess.run(["dxdiag", "/x", output_path], check=False)
        
        # dxdiag forks and writes asynchronously; polling is mandatory.
        # Max wait: 15 seconds (30 iterations of 0.5s) to reduce blocking duration.
        for _ in range(30):
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                try:
                    tree = ET.parse(output_path)
                    root = tree.getroot()
                    
                    return {
                        "DirectXVersion": root.findtext(".//DirectXVersion"),
                        "DisplayDevices":[{c.tag: c.text for c in d if c.text} for d in root.findall(".//DisplayDevice")],
                        ##"SoundDevices":[{c.tag: c.text for c in d if c.text} for d in root.findall(".//SoundDevice")],
                        "LogicalDisks":[{c.tag: c.text for c in d if c.text} for d in root.findall(".//LogicalDisk")]
                    }
                except ET.ParseError:
                    # File exists but is actively being written to; continue polling
                    pass
            time.sleep(0.5)
            
        raise RuntimeError("DXDiag timed out during asynchronous file generation.")