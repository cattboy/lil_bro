import os
import subprocess
import time
from typing import Optional, Dict
from ..utils.formatting import print_step, print_step_done, print_error, print_info, prompt_approval

class CinebenchOrchestrator:
    def __init__(self, executable_path: Optional[str] = None):
        # Default to the local bench-exe folder in the repo (CWD/lil_bro/src/bench-exe).
        # This makes it easy to run a "dummy" Cinebench binary during development.
        if executable_path:
            self.executable_path = executable_path
        else:
            repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            self.executable_path = os.path.join(repo_root, "bench-exe", "Cinebench.exe")

    def is_installed(self) -> bool:
        """Checks if Cinebench is available at the expected path."""
        return os.path.exists(self.executable_path)

    def find_cinebench(self):
        """Attempts to locate Cinebench if not in default path."""
        common_paths = [
            os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")), "bench-exe", "Cinebench.exe"),
            "C:\\Program Files\\Maxon Cinema 4D 2026\\Cinebench.exe",
            "C:\\Program Files\\Maxon Cinema 4D 2024\\Cinebench.exe",
            "C:\\Users\\Public\\Desktop\\Cinebench.exe"
        ]
        for p in common_paths:
            if os.path.exists(p):
                self.executable_path = p
                return True
        return False
        
    def run_benchmark(self, run_all: bool = True) -> Dict[str, str]:
        """
        Runs Cinebench via CLI.
        Warning: Cinebench CLI behavior varies, usually console output isn't easily pipeable.
        We run it and capture what we can, or rely on logs if it produces them.
        """
        if not self.is_installed() and not self.find_cinebench():
            print_error(f"Cinebench not found at {self.executable_path}.")
            if prompt_approval("Would you like to skip the benchmark phase for now?"):
                return {"status": "skipped", "message": "Cinebench not installed"}
            else:
                return {"status": "error", "message": "Cinebench required but not found"}
                
        print_step(f"Running Cinebench 2026{' (All Tests)' if run_all else ' (CPU Multicore)'}")
        print_info("This will take several minutes. Your PC will experience high load. Do not use it during the test.")
        
        args = [self.executable_path]
        if run_all:
            args.append("g_CinebenchAllTests=true")
        else:
            args.append("g_CinebenchCpuXTest=true")
            
        try:
            # On Windows, we need 'start /b /wait "parentconsole" ...' to capture CLI output.
            # Building the shell string:
            cmd = f'start /b /wait "parentconsole" "{self.executable_path}" ' + " ".join(args[1:])
            
            # Since we're likely testing on Linux dummy env or running from pure python,
            # we use subprocess directly.
            result = subprocess.run(
                cmd if os.name == 'nt' else ["echo", "Dummy Cinebench Score: CPU Multi: 15320, GPU: 24310"],
                shell=(os.name == 'nt'),
                capture_output=True,
                text=True
            )
            
            print_step_done(True)
            
            # Parse output. Actual format depends heavily on Maxon's current CLI output.
            # Example heuristic parsing:
            out = result.stdout + "\n" + result.stderr
            scores = {}
            for line in out.splitlines():
                if "pts" in line.lower() or "score" in line.lower():
                    # Simplified placeholder parsing logic
                    if "multicore" in line.lower() or "cpu" in line.lower():
                        scores["CPU_Multi"] = line.strip()
                    elif "gpu" in line.lower():
                        scores["GPU"] = line.strip()
                        
            # If parsing failed but it ran (common with GUI tools launched via CLI)
            if not scores and os.name != 'nt':
                 scores = {"CPU_Multi": "15320 pts", "GPU": "24310 pts"} # Dummy data for dev
                 
            return {
                "status": "success",
                "raw_output": out[:500] + "...", # truncate for log
                "scores": scores
            }
            
        except Exception as e:
            print_step_done(False)
            print_error(f"Cinebench failed: {e}")
            return {"status": "error", "message": str(e)}

    def get_lhm_peak_temps(self) -> Dict[str, float]:
        """
        While or after the benchmark, read LibreHardwareMonitor to get peak temps.
        For now, this probes the immediate temp; a real implementation might need a 
        background thread polling LHM during the test.
        """
        import urllib.request
        import json
        try:
            req = urllib.request.Request("http://localhost:8085/data.json")
            with urllib.request.urlopen(req, timeout=2) as response:
                data = json.loads(response.read())
                
            # Naive recursive search for temperatures
            temps = {}
            def find_temps(node, path=""):
                if isinstance(node, dict):
                    if node.get("Text") == "Temperatures" and "Children" in node:
                        for child in node["Children"]:
                            temps[path + child.get("Text", "")] = float(child.get("Value", "0").replace(" °C", ""))
                    elif "Children" in node:
                         for child in node["Children"]:
                             find_temps(child, path + node.get("Text", "") + " -> ")
                elif isinstance(node, list):
                    for item in node:
                        find_temps(item, path)
                        
            find_temps(data)
            return temps
        except Exception as e:
            return {"error": str(e)}
