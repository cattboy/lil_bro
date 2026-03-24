"""Shared thermal safety gate -- used before both benchmark phases."""

from src.benchmarks.thermal_monitor import fetch_snapshot
from src.agent_tools.thermal_guidance import check_idle_thermals
from src.utils.formatting import print_info, print_success, print_warning, prompt_approval


def thermal_safety_gate(
    lhm_available: bool,
    skip_message: str = "Skipping benchmark -- let your PC cool down and try again.",
    approval_prompt: str = "Temperatures are elevated. Run the benchmark anyway?",
) -> bool:
    """
    Checks idle thermals before a benchmark run.

    Args:
        lhm_available: Whether LHM sidecar is running.
        skip_message: Message to print if user declines.
        approval_prompt: The prompt shown when temps are elevated.

    Returns:
        True if the benchmark should be SKIPPED, False if safe to proceed.
    """
    if not lhm_available:
        return False  # No thermal data -- proceed

    print_info("Checking idle temperatures before benchmark...")
    idle_temps = fetch_snapshot()
    idle_check = check_idle_thermals(idle_temps)

    if idle_check["safe"]:
        print_success(idle_check["message"])
        return False  # Safe -- don't skip

    print_warning(idle_check["message"])
    if not prompt_approval(approval_prompt):
        print_info(skip_message)
        return True  # User chose to skip

    return False  # User approved despite high temps
