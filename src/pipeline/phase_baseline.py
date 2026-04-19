"""Phase 3 — Baseline Benchmark: Cinebench run + thermal monitoring."""

from src.pipeline.base import PipelineContext, PhaseResult
from src.benchmarks.cinebench import BenchmarkRunner
from src.pipeline.thermal_gate import require_thermal_protection, thermal_safety_gate
from src.utils.formatting import (
    print_header, print_info, print_success, print_warning,
)
from src.utils.action_logger import action_logger
from src.utils.debug_logger import get_debug_logger


_SKIP_RESULT     = {"status": "skipped", "message": "Benchmark skipped — no thermal protection."}
_SKIP_RESULT_HOT = {"status": "skipped", "message": "Benchmark skipped — idle temps too high."}


class BaselineBenchPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 3: Baseline Benchmark")
        print_header("Phase 3: Baseline Benchmark")

        if require_thermal_protection("BaselineBench", ctx):
            ctx.baseline_result = dict(_SKIP_RESULT)
            ctx.peak_temps = {}
            return PhaseResult("skipped", "No thermal protection available")

        benchmark_skipped = thermal_safety_gate(ctx.lhm_available)

        if benchmark_skipped:
            ctx.baseline_result = dict(_SKIP_RESULT_HOT)
            ctx.peak_temps = {}
            action_logger.log_action(
                "BaselineBench",
                "Benchmark skipped — idle temps too high",
                details="Idle temperatures exceeded safe threshold or user declined.",
                outcome="SKIPPED",
            )
            return PhaseResult("skipped", "Idle temperatures too high")

        ctx.runner = BenchmarkRunner()
        ctx.thermal.start()
        print_info("Thermal monitoring active -- sampling temperatures during benchmark.")
        try:
            ctx.baseline_result = ctx.runner.run_benchmark(
                full_suite=False, lhm_available=ctx.lhm_available
            )
        finally:
            ctx.thermal.stop()

        if ctx.baseline_result.get("status") == "success":
            print_success("Baseline Benchmark Complete!")
            print_info(f"Scores: {ctx.baseline_result.get('scores', {})}")

        ctx.peak_temps = ctx.thermal.get_peak_temps()
        if ctx.peak_temps:
            cpu_peak = ctx.thermal.get_cpu_peak()
            gpu_peak = ctx.thermal.get_gpu_peak()
            parts = []
            if cpu_peak is not None:
                parts.append(f"CPU: {cpu_peak:.1f}\u00b0C")
            if gpu_peak is not None:
                parts.append(f"GPU: {gpu_peak:.1f}\u00b0C")
            if parts:
                print_info(
                    f"Peak temps during benchmark: {', '.join(parts)} "
                    f"({ctx.thermal.sample_count} samples)"
                )
        else:
            print_warning("Thermal monitor ran but captured no temperature data.")
        return PhaseResult("completed", "Baseline benchmark complete")
