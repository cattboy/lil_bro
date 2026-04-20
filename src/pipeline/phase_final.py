"""Phase 5 — Final Verification Benchmark: re-run and compare deltas."""

from src.pipeline.base import PipelineContext, PhaseResult
from src.pipeline.thermal_gate import run_thermal_guard
from src.utils.formatting import print_header, print_info, print_success
from src.utils.debug_logger import get_debug_logger


class FinalBenchPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 5: Final Verification Benchmark")
        print_header("Phase 5: Final Verification Benchmark")

        # Guard: if Phase 3 was skipped (ctx.runner never set), skip Phase 5 too.
        if ctx.runner is None:
            print_info("Final benchmark was skipped -- baseline benchmark did not run.")
            return PhaseResult("skipped", "Baseline benchmark did not run")

        # Guard: if the baseline didn't produce scores, there's nothing to compare.
        baseline_status = ctx.baseline_result.get("status")
        if baseline_status != "success":
            if baseline_status == "aborted":
                print_info("Baseline benchmark was aborted — skipping final benchmark.")
            else:
                print_info("Baseline benchmark did not complete — skipping final benchmark.")
            return PhaseResult("skipped", "Baseline benchmark did not complete")

        if run_thermal_guard(
            "FinalBench", ctx,
            skip_message="Skipping final benchmark.",
            approval_prompt="Temperatures are elevated. Run the final benchmark anyway?",
        ):
            print_info("Final benchmark was skipped -- no comparison available.")
            return PhaseResult("skipped", "Thermal safety gate triggered")

        ctx.thermal.start()
        try:
            final = ctx.runner.run_benchmark(full_suite=True, lhm_available=ctx.lhm_available)
        finally:
            ctx.thermal.stop()

        if final.get("status") == "success":
            print_success("Final Benchmark Complete!")
            print_info(f"After:  {final.get('scores', {})}")
            print_info(f"Before: {ctx.baseline_result.get('scores', {})}")
        return PhaseResult("completed", "Final benchmark complete")
