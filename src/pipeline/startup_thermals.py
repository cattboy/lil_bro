"""Startup thermal scan — runs once at launch before the main menu.

Takes a single temperature snapshot immediately after banner display so the
user sees live temps before choosing any option. Prints activity text before
starting LHM so the app never appears frozen during the ~2-5s sidecar startup.
"""

import time
from colorama import Fore

from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.benchmarks.thermal_monitor import fetch_snapshot
from src.agent_tools.thermal_guidance import (
    check_idle_thermals,
    CPU_IDLE_WARN,
    GPU_IDLE_WARN,
)
from src.utils.formatting import (
    print_info,
    print_success,
    print_warning,
    print_dim,
    print_accent,
    print_key_value,
    print_step,
    print_step_done,
)
from src.utils.pawnio_check import is_pawnio_installed

# LHM HTTP becomes ready before hardware sensors fully populate.
# Retry a few times so we don't show "No sensor readings" on a healthy system.
_SENSOR_RETRIES = 10
_SENSOR_RETRY_DELAY = 0.5  # seconds between attempts


def run_startup_thermal_scan() -> tuple[LHMSidecar, bool]:
    """Start LHM, take a single temperature snapshot, and display the results.

    Prints "Scanning idle temperatures..." BEFORE starting LHM so the user
    sees activity immediately rather than a blank screen during sidecar startup.

    Returns:
        (lhm, lhm_available)
        lhm: the LHMSidecar instance — caller must call lhm.stop() on exit.
        lhm_available: True if LHM started and responded (False if unavailable).
    """
    print_info("Scanning idle temperatures...")

    lhm = LHMSidecar()
    lhm_available = lhm.start()  # sidecar prints its own "Launching..." progress

    if not lhm_available:
        print_dim("Thermal sensors unavailable — temperature display skipped.")
        return lhm, False

    # Retry until sensors populate (LHM HTTP-ready ≠ sensors enumerated)
    temps: dict = {}
    attempt = 0
    for attempt in range(_SENSOR_RETRIES):
        temps = fetch_snapshot()
        if temps:
            break
        if attempt == 0:
            print_step("Waiting for sensor data")
        if attempt < _SENSOR_RETRIES - 1:
            time.sleep(_SENSOR_RETRY_DELAY)

    if attempt > 0:
        print_step_done(bool(temps))

    result = check_idle_thermals(temps)

    cpu_temp = result.get("cpu_temp")
    gpu_temp = result.get("gpu_temp")

    if cpu_temp is None and gpu_temp is None:
        print_accent("  No sensor readings returned — temperature display skipped.  "
                  "lil_bro inhales motherboard electrons using LibreHardwareMonitor."
                  "\n  Visit open source https://github.com/LibreHardwareMonitor/LibreHardwareMonitor ")
        if not is_pawnio_installed():
            print_accent(
                "  Hint: lil_bro auto-installs the PawnIO.sys driver to see inside your PC. If it failed for some reason, retry running lil_bro.\n"
                "  See https://github.com/namazso/PawnIO.Setup/releases to install it yourself."
            )
        print()
        return lhm, True

    if cpu_temp is not None:
        cpu_color = Fore.YELLOW if cpu_temp >= CPU_IDLE_WARN else Fore.GREEN
        print_key_value("CPU Temp", f"{cpu_temp:.0f}°C", value_color=cpu_color)

    if gpu_temp is not None:
        gpu_color = Fore.YELLOW if gpu_temp >= GPU_IDLE_WARN else Fore.GREEN
        print_key_value("GPU Temp", f"{gpu_temp:.0f}°C", value_color=gpu_color)

    if result["safe"]:
        print_success(result["message"])
    else:
        print_warning(result["message"])

    print()
    return lhm, True
