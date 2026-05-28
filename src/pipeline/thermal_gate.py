"""Shared thermal safety gate -- used before both benchmark phases."""

from src.pipeline.base import PipelineContext
from src.benchmarks.thermal_monitor import fetch_snapshot
from src.agent_tools.thermal_guidance import check_idle_thermals
from src.utils.formatting import print_info, print_success, print_warning, prompt_approval
from src.utils.action_logger import action_logger


_DEFAULT_THERMAL_APPROVAL = "Temperatures are elevated. Run the benchmark anyway?"


def require_thermal_protection(
    phase_name: str,
    ctx: PipelineContext,
    snapshot: dict | None = None,
) -> bool:
    """Check that LHM and sensor data are available before a benchmark.

    Returns True if the benchmark should be SKIPPED (missing thermal protection).
    Logs and prints warnings when skipping.

    ``snapshot`` is an optional pre-fetched LHM sensor read; pass it when the
    caller already has one in hand to avoid a redundant HTTP round-trip (the
    ``fetch_snapshot()`` call below). ``run_thermal_guard`` reuses the same
    snapshot for both the presence check and ``check_idle_thermals``.
    """
    if not ctx.lhm_available:
        action_logger.log_action(
            phase_name,
            "Benchmark skipped — LHM unavailable",
            details="No thermal protection available. LHM did not load.",
            outcome="SKIPPED",
        )
        print_warning(
            f"LibreHardwareMonitor is not running — skipping {phase_name.lower()} benchmark. "
            "Thermal monitoring is required to run safely."
        )
        return True

    if snapshot is None:
        snapshot = fetch_snapshot()
    if not snapshot:
        action_logger.log_action(
            phase_name,
            "Benchmark skipped — no sensor data",
            details="LHM is running but returned no temperature readings. Cannot guarantee thermal safety.",
            outcome="SKIPPED",
        )
        print_warning(
            f"LHM is running but no temperature sensor data is available — skipping {phase_name.lower()} benchmark just incase. "
            "lil_bro always lookin' out for the fam."
        )
        return True

    return False


def run_thermal_guard(
    phase_name: str,
    ctx: PipelineContext,
    skip_message: str = "Benchmark skipped — idle temps too high.",
    approval_prompt: str = _DEFAULT_THERMAL_APPROVAL,
) -> bool:
    """Combined pre-benchmark thermal check: requires LHM + sensor data + safe idle temps.

    Returns True if the benchmark should be skipped.
    """
    # Single fetch -- shared by the presence check inside
    # require_thermal_protection and check_idle_thermals below. Skip the
    # fetch when LHM is down; require_thermal_protection short-circuits on
    # the unavailable branch before reading the snapshot.
    snapshot = fetch_snapshot() if ctx.lhm_available else None
    if require_thermal_protection(phase_name, ctx, snapshot=snapshot):
        return True

    print_info("Checking idle temperatures before benchmark...")
    idle_check = check_idle_thermals(snapshot)

    if idle_check["safe"]:
        print_success(idle_check["message"])
        return False

    print_warning(idle_check["message"])
    if not prompt_approval(approval_prompt):
        print_info(skip_message)
        return True  # User chose to skip

    return False  # User approved despite high temps
