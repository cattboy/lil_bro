import subprocess
import re
from ..utils.errors import ScannerError
from ..utils.formatting import print_step, print_step_done, print_warning, print_success, print_error

# Common Windows Power Plan GUIDs
KNOWN_PLANS = {
    "e9a42b02-d5df-448d-aa00-03f14749eb61": "Ultimate Performance",
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": "High Performance",
    "381b4222-f694-41f0-9685-ff5bb260df2e": "Balanced",
    "a1841308-3541-4fab-bc81-f71556f20b4a": "Power Saver",
}

def get_active_power_plan() -> tuple[str, str]:
    """
    Runs powercfg /getactivescheme to find the active power plan.
    Returns:
        (guid, name)
    """
    try:
        # Example output: "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)"
        result = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            check=True
        )
        
        output = result.stdout.strip()
        
        # Extract GUID using regex
        match = re.search(r"GUID:\s*([a-f0-9\-]+)", output, re.IGNORECASE)
        if not match:
             raise ScannerError(f"Could not parse powercfg output: {output}")
             
        guid = match.group(1).lower()
        
        # Try to extract the name from brackets, or fallback to our known list
        name_match = re.search(r"\((.+?)\)", output)
        if name_match:
            name = name_match.group(1)
        else:
            name = KNOWN_PLANS.get(guid, "Unknown Plan")
            
        return guid, name
        
    except FileNotFoundError:
        raise ScannerError("powercfg executable not found. Are you on Windows?")
    except subprocess.CalledProcessError as e:
        raise ScannerError(f"powercfg failed with error code {e.returncode}: {e.stderr}")
    except Exception as e:
        raise ScannerError(f"Unexpected error getting power plan: {e}")

def check_power_plan() -> dict:
    """
    Runs the Power Plan check.
    """
    print_step("Scanning Active Power Plan")
    
    try:
        guid, name = get_active_power_plan()
        print_step_done(True)
        
        result = {
            "active_plan": name,
            "guid": guid,
            "status": "OK"
        }
        
        # Check if it's High or Ultimate performance
        is_high_perf = (
            guid == "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" or  # High Performance
            guid == "e9a42b02-d5df-448d-aa00-03f14749eb61" or  # Ultimate Performance
            "performance" in name.lower()
        )
        
        if not is_high_perf:
            result["status"] = "WARNING"
            result["message"] = f"Current power plan is '{name}'. For gaming, 'High Performance' or 'Ultimate Performance' is recommended to prevent core parking and latency."
            print_warning(result["message"])
        else:
            result["message"] = f"Power plan is optimal: '{name}'."
            print_success(result["message"])
            
        return result
        
    except ScannerError as e:
        print_step_done(False)
        print_error(str(e))
        return {"active_plan": "Unknown", "guid": "", "status": "ERROR", "message": str(e)}
