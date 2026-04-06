"""Phase 3 — Baseline Benchmark: Cinebench run + thermal monitoring."""

from src.pipeline.base import PipelineContext
from src.benchmarks.cinebench import BenchmarkRunner
from src.benchmarks.thermal_monitor import fetch_snapshot
from src.pipeline.thermal_gate import thermal_safety_gate
from src.utils.formatting import (
    print_header, print_info, print_success, print_warning,
)
from src.utils.action_logger import action_logger
from src.utils.debug_logger import get_debug_logger


class BaselineBenchPhase:
    def run(self, ctx: PipelineContext) -> None:
        log = get_debug_logger()
        log.info("Phase 3: Baseline Benchmark")
        print_header("Phase 3: Baseline Benchmark")

        if not ctx.lhm_available:
            action_logger.log_action(
                "BaselineBench",
                "Benchmark skipped — LHM unavailable",
                details="No thermal protection available. LHM did not load.",
                outcome="SKIPPED",
            )
            print_warning(
                "LibreHardwareMonitor is not running — skipping baseline benchmark. "
                "Thermal monitoring is required to run safely."
            )
            ctx.baseline_result = {
                "status": "skipped",
                "message": "LHM unavailable — no thermal protection.",
            }
            ctx.peak_temps = {}
            return

        if not fetch_snapshot():
            action_logger.log_action(
                "BaselineBench",
                "Benchmark skipped — no sensor data",
                details="LHM is running but returned no temperature readings. Cannot guarantee thermal safety.",
                outcome="SKIPPED",
            )
            print_warning(
                "LHM is running but no sensor data is available — skipping benchmark. "
                "Run lil_bro as administrator to install the PawnIO thermal driver."
            )
            ctx.baseline_result = {
                "status": "skipped",
                "message": "No sensor data — thermal protection unavailable.",
            }
            ctx.peak_temps = {}
            return

        ctx.runner = BenchmarkRunner()
        benchmark_skipped = thermal_safety_gate(ctx.lhm_available)

        ctx.baseline_result = {"status": "skipped", "message": "Skipped due to high idle temps"}
        ctx.peak_temps = {}

        if benchmark_skipped:
            action_logger.log_action(
                "BaselineBench",
                "Benchmark skipped — idle temps too high",
                details="Idle temperatures exceeded safe threshold or user declined.",
                outcome="SKIPPED",
            )
            return

        if ctx.lhm_available:
            ctx.thermal.start()
            print_info("Thermal monitoring active -- sampling temperatures during benchmark.")

        ctx.baseline_result = ctx.runner.run_benchmark(
            full_suite=False, lhm_available=ctx.lhm_available
        )

        if ctx.baseline_result.get("status") == "success":
            print_success("Baseline Benchmark Complete!")
            print_info(f"Scores: {ctx.baseline_result.get('scores', {})}")

        if ctx.lhm_available:
            ctx.thermal.stop()
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
