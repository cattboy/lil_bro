"""Phase 5 — Final Verification Benchmark: re-run and compare deltas."""

from src.pipeline.base import PipelineContext
from src.pipeline.thermal_gate import thermal_safety_gate
from src.utils.formatting import print_header, print_info, print_success
from src.utils.debug_logger import get_debug_logger


class FinalBenchPhase:
    def run(self, ctx: PipelineContext) -> None:
        log = get_debug_logger()
        log.info("Phase 5: Final Verification Benchmark")
        print_header("Phase 5: Final Verification Benchmark")

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

        final = ctx.runner.run_benchmark(full_suite=True)

        if ctx.lhm_available:
            ctx.thermal.stop()

        if final.get("status") == "success":
            print_success("Final Benchmark Complete!")
            print_info(f"After:  {final.get('scores', {})}")
            print_info(f"Before: {ctx.baseline_result.get('scores', {})}")
