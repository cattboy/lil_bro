"""Phase 5 — Final Verification Benchmark: re-run and compare deltas."""

from src.pipeline.base import PipelineContext
from src.benchmarks.thermal_monitor import fetch_snapshot
from src.pipeline.thermal_gate import thermal_safety_gate
from src.utils.formatting import print_header, print_info, print_success, print_warning
from src.utils.action_logger import action_logger
from src.utils.debug_logger import get_debug_logger


class FinalBenchPhase:
    def run(self, ctx: PipelineContext) -> None:
        log = get_debug_logger()
        log.info("Phase 5: Final Verification Benchmark")
        print_header("Phase 5: Final Verification Benchmark")

        if not ctx.lhm_available:
            action_logger.log_action(
                "FinalBench",
                "Benchmark skipped — LHM unavailable",
                details="No thermal protection available. LHM did not load.",
                outcome="SKIPPED",
            )
            print_warning(
                "LibreHardwareMonitor is not running — skipping final benchmark. "
                "Thermal monitoring is required to run safely."
            )
            print_info("Final benchmark was skipped -- no comparison available.")
            return

        if not fetch_snapshot():
            action_logger.log_action(
                "FinalBench",
                "Benchmark skipped — no sensor data",
                details="LHM is running but returned no temperature readings. Cannot guarantee thermal safety.",
                outcome="SKIPPED",
            )
            print_warning(
                "LHM is running but no sensor data is available — skipping final benchmark. "
                "Run lil_bro as administrator to install the PawnIO thermal driver."
            )
            print_info("Final benchmark was skipped -- no comparison available.")
            return

        final_skipped = thermal_safety_gate(
            ctx.lhm_available,
            skip_message="Skipping final benchmark.",
            approval_prompt="Temperatures are elevated. Run the final benchmark anyway?",
        )

        if final_skipped:
            print_info("Final benchmark was skipped -- no comparison available.")
            return

        if ctx.lhm_available:
            ctx.thermal.start()

        final = ctx.runner.run_benchmark(full_suite=True, lhm_available=ctx.lhm_available)

        if ctx.lhm_available:
            ctx.thermal.stop()

        if final.get("status") == "success":
            print_success("Final Benchmark Complete!")
            print_info(f"After:  {final.get('scores', {})}")
            print_info(f"Before: {ctx.baseline_result.get('scores', {})}")
