import subprocess
import re
from ..utils.errors import ScannerError
from ..utils.action_logger import action_logger

# Common Windows Power Plan GUIDs
KNOWN_PLANS = {
    "e9a42b02-d5df-448d-aa00-03f14749eb61": "Ultimate Performance",
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c": "High Performance",
    "381b4222-f694-41f0-9685-ff5bb260df2e": "Balanced",
    "a1841308-3541-4fab-bc81-f71556f20b4a": "Power Saver",
}

_PERF_GUIDS = {
    "e9a42b02-d5df-448d-aa00-03f14749eb61",  # Ultimate Performance
    "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c",  # High Performance
}

def analyze_power_plan(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected power plan state from specs dict.
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    plan = specs.get("PowerPlan", {})
    guid = plan.get("guid", "")
    name = plan.get("name", "Unknown")

    is_perf = (
        guid in _PERF_GUIDS or
        "performance" in name.lower() or
        "ultimate" in name.lower()
    )

    if not is_perf:
        return {
            "check": "power_plan",
            "status": "WARNING",
            "current": name,
            "expected": "High Performance or Ultimate Performance",
            "message": f"Power plan is '{name}'. Switch to High Performance for gaming.",
            "can_auto_fix": True,
        }
    return {
        "check": "power_plan",
        "status": "OK",
        "current": name,
        "expected": name,
        "message": f"Power plan is optimal: '{name}'.",
        "can_auto_fix": False,
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

def list_available_plans() -> list[tuple[str, str]]:
    """
    Runs powercfg /list to get all available power plans.
    Returns a list of (guid, name) tuples.
    """
    try:
        result = subprocess.run(
            ["powercfg", "/list"],
            capture_output=True,
            text=True,
            check=True
        )
        
        plans = []
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line.lower().startswith("power scheme guid"):
                continue
                
            match = re.search(r"GUID:\s*([a-f0-9\-]+)", line, re.IGNORECASE)
            if match:
                guid = match.group(1).lower()
                name_match = re.search(r"\((.+?)\)", line)
                name = name_match.group(1) if name_match else KNOWN_PLANS.get(guid, "Unknown Plan")
                plans.append((guid, name))
                
        return plans
        
    except FileNotFoundError:
        raise ScannerError("powercfg executable not found.")
    except subprocess.CalledProcessError as e:
        raise ScannerError(f"powercfg list failed: {e.stderr}")
    except Exception as e:
        raise ScannerError(f"Unexpected error listing power plans: {e}")

def set_active_plan(guid: str) -> None:
    """Activates the given power plan GUID."""
    try:
        subprocess.run(
            ["powercfg", "/setactive", guid],
            capture_output=True,
            text=True,
            check=True
        )
        action_logger.log_action("PowerCfg", f"Switched active power plan to {guid}", f"Execution: powercfg /setactive {guid}")
    except subprocess.CalledProcessError as e:
        raise ScannerError(f"Failed to activate power plan: {e.stderr}")

def create_high_performance_plan() -> tuple[str, str]:
    """
    Creates a new High Performance plan from the built-in template.
    Returns the new (guid, name).
    """
    # built-in HP template
    template_guid = "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c" 
    try:
        result = subprocess.run(
            ["powercfg", "/duplicatescheme", template_guid],
            capture_output=True,
            text=True,
            check=True
        )
        # Output is like: Power Scheme GUID: 1234...  (High performance)
        match = re.search(r"GUID:\s*([a-f0-9\-]+)", result.stdout, re.IGNORECASE)
        if not match:
             raise ScannerError(f"Could not parse duplicatescheme output: {result.stdout}")
        
        guid = match.group(1).lower()
        action_logger.log_action("PowerCfg", f"Created new High Performance plan {guid}", f"Execution: powercfg /duplicatescheme {template_guid}")
        return guid, "High performance"
    except subprocess.CalledProcessError as e:
        raise ScannerError(f"Failed to create new power plan: {e.stderr}")
