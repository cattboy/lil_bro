"""Phase 4b — Benchmark Opt-In: ask the user whether to run PRE/POST Cinebench."""

from src.pipeline.base import PipelineContext, PhaseResult
from src.utils.formatting import print_header, print_info, prompt_benchmark_optin
from src.utils.debug_logger import get_debug_logger


class BenchmarkOptInPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 4: Benchmark Opt-In")
        print_header("Phase 4: Benchmark Opt-In")

        if not ctx.lhm_available:
            log.info("LHM unavailable — skipping benchmark opt-in (no thermal protection)")
            print_info("Thermal monitoring unavailable — benchmarks require LHM. Skipping.")
            ctx.run_benchmarks = False
            return PhaseResult("skipped", "No thermal protection — benchmarks unavailable")

        ctx.run_benchmarks = prompt_benchmark_optin()

        if ctx.run_benchmarks:
            log.info("User opted in to PRE/POST benchmarks")
            print_info("Benchmarks enabled — PRE run will start now.")
        else:
            log.info("User opted out of benchmarks")
            print_info("Skipping benchmarks — fixes will be applied directly.")

        return PhaseResult("completed", f"Benchmark opt-in: {ctx.run_benchmarks}")
