"""Phase 7 — Final Verification Benchmark: re-run and compare deltas."""

from src.pipeline.base import PipelineContext, PhaseResult
from src.pipeline.thermal_gate import run_thermal_guard
from src.utils.formatting import print_header, print_info, print_success
from src.utils.debug_logger import get_debug_logger


def _print_applied_fixes_summary(ctx) -> None:
    """Print what was applied when benchmark comparison is unavailable."""
    if ctx.fixes_applied == 0:
        print_info("No configuration changes were applied.")
        return
    print_success(f"{ctx.fixes_applied} fix(es) applied successfully.")
    for proposal in ctx.approved_proposals:
        print_info(f"  • {proposal.get('finding', '').replace('_', ' ').title()}")


class FinalBenchPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 7: Final Verification Benchmark")
        print_header("Phase 7: Final Verification Benchmark")

        # Guard: user explicitly opted out — show applied-fixes summary and exit cleanly.
        if ctx.run_benchmarks is False:
            _print_applied_fixes_summary(ctx)
            return PhaseResult(
                "completed" if ctx.fixes_applied > 0 else "skipped",
                "Fixes applied without benchmark comparison",
            )

        # Guard: PRE benchmark never ran (e.g. thermal gate fired after opt-in, or opt-in skipped).
        if ctx.runner is None:
            print_info("Final benchmark was skipped -- baseline benchmark did not run.")
            _print_applied_fixes_summary(ctx)
            return PhaseResult("skipped", "Baseline benchmark did not run")

        # Guard: PRE ran but did not complete successfully.
        baseline_status = ctx.baseline_result.get("status")
        if baseline_status != "success":
            if baseline_status == "aborted":
                print_info("Baseline benchmark was aborted — skipping final benchmark.")
            else:
                print_info("Baseline benchmark did not complete — skipping final benchmark.")
            _print_applied_fixes_summary(ctx)
            return PhaseResult("skipped", "Baseline benchmark did not complete")

        # Guard: nothing changed — no point benchmarking an unchanged machine.
        if ctx.fixes_applied == 0:
            print_info("No configuration changes were applied -- skipping final benchmark.")
            from src.utils.formatting import notify_benchmark_score
            notify_benchmark_score("final_skipped", {}, None)
            return PhaseResult("skipped", "No config changes applied")

        if run_thermal_guard(
            "FinalBench", ctx,
            skip_message="Skipping final benchmark.",
            approval_prompt="Temperatures are elevated. Run the final benchmark anyway?",
        ):
            print_info("Final benchmark was skipped -- no comparison available.")
            _print_applied_fixes_summary(ctx)
            return PhaseResult("skipped", "Thermal safety gate triggered")

        ctx.thermal.start()
        try:
            final = ctx.runner.run_benchmark(full_suite=False, lhm_available=ctx.lhm_available)
        finally:
            ctx.thermal.stop()

        if final.get("status") == "success":
            print_success("Final Benchmark Complete!")
            print_info(f"After:  {final.get('scores', {})}")
            print_info(f"Before: {ctx.baseline_result.get('scores', {})}")
            from src.utils.formatting import notify_benchmark_score
            notify_benchmark_score("final", final.get("scores", {}), None)

        return PhaseResult("completed", "Final benchmark complete")
