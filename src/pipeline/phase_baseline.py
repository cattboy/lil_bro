"""Phase 5 — Baseline Benchmark: Cinebench run + thermal monitoring."""

from src.pipeline.base import PipelineContext, PhaseResult
from src.benchmarks.cinebench import BenchmarkRunner
from src.pipeline.thermal_gate import run_thermal_guard
from src.utils.formatting import (
    print_header, print_info, print_success, print_warning,
    prompt_approval,
)
from src.utils.action_logger import action_logger
from src.utils.debug_logger import get_debug_logger


_SKIP_RESULT_HOT = {"status": "skipped", "message": "Benchmark skipped — idle temps too high."}


class BaselineBenchPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 5: Baseline Benchmark")
        print_header("Phase 5: Baseline Benchmark")

        if ctx.run_benchmarks is False:
            return PhaseResult("skipped", "User opted out of benchmarks")

        ctx.runner = BenchmarkRunner()
        if not ctx.runner.has_cinebench:
            ctx.baseline_result = ctx.runner.run_benchmark(full_suite=False, lhm_available=ctx.lhm_available)
            ctx.peak_temps = {}
            return PhaseResult("skipped", "Cinebench not available")

        if run_thermal_guard("BaselineBench", ctx):
            ctx.baseline_result = dict(_SKIP_RESULT_HOT)
            ctx.peak_temps = {}
            action_logger.log_action(
                "BaselineBench",
                "Benchmark skipped — thermal check failed",
                details="LHM unavailable, no sensor data, or idle temps too high.",
                outcome="SKIPPED",
            )
            return PhaseResult("skipped", "Thermal check failed")

        ctx.thermal.start()
        print_info("Thermal monitoring active -- sampling temperatures during benchmark.")
        try:
            ctx.baseline_result = ctx.runner.run_benchmark(
                full_suite=False, lhm_available=ctx.lhm_available
            )
        finally:
            ctx.thermal.stop()

        status = ctx.baseline_result.get("status")
        if status == "success":
            print_success("Baseline Benchmark Complete!")
            print_info(f"Scores: {ctx.baseline_result.get('scores', {})}")
        elif ctx.approved_proposals:
            n = len(ctx.approved_proposals)
            reason = "was cancelled" if status == "aborted" else "failed"
            if prompt_approval(f"Benchmark {reason}. Apply the {n} approved fix(es) anyway?"):
                ctx.cancel_override = True
            else:
                ctx.skip_apply = True

        ctx.peak_temps = ctx.thermal.get_peak_temps()
        cpu_peak = ctx.thermal.get_cpu_peak()
        gpu_peak = ctx.thermal.get_gpu_peak()

        if ctx.peak_temps:
            parts = []
            if cpu_peak is not None:
                parts.append(f"CPU: {cpu_peak:.1f}°C")
            if gpu_peak is not None:
                parts.append(f"GPU: {gpu_peak:.1f}°C")
            if parts:
                print_info(
                    f"Peak temps during benchmark: {', '.join(parts)} "
                    f"({ctx.thermal.sample_count} samples)"
                )
        else:
            print_warning("Thermal monitor ran but captured no temperature data.")

        if status == "success":
            from src.utils.formatting import notify_benchmark_score
            notify_benchmark_score(
                "baseline",
                ctx.baseline_result.get("scores", {}),
                cpu_peak,
            )

        return PhaseResult("completed", "Baseline benchmark complete")
