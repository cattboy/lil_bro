"""Phase 2 — Deep System Scan: LHM start, spec dump, hardware preview."""

import json

from src.pipeline.base import PipelineContext, PhaseResult
from src.collectors.spec_dumper import dump_system_specs
from src.utils.dump_parser import extract_hardware_summary
from src.agent_tools.mouse import check_polling_rate
from src.utils.formatting import (
    print_header, print_success, print_info, print_key_value,
    notify_mouse_poll_result, prompt_mouse_ready,
)
from src.utils.debug_logger import get_debug_logger


class ScanPhase:
    def run(self, ctx: PipelineContext) -> PhaseResult:
        log = get_debug_logger()
        log.info("Phase 2: Deep System Scan")
        print_header("Phase 2: Deep System Scan")

        ctx.lhm_available = ctx.lhm.start()
        if ctx.lhm_available:
            print_success("Thermal monitoring active on port 8085.")
        else:
            log.warning("LHM sidecar unavailable — continuing without thermal monitoring")
            print_info("Continuing without thermal monitoring -- Cinebench will still run.")

        prompt_mouse_ready()
        ctx.mouse_result = check_polling_rate()
        notify_mouse_poll_result(ctx.mouse_result)

        # Fresh-first, snapshot-fallback. The pipeline always re-scans live
        # system state; the startup snapshot preloaded into ctx.specs is kept
        # only as a degraded-mode fallback for when a fresh dump fails.
        # Reusing the snapshot as the primary input let a second pipeline run
        # re-detect and re-apply already-applied fixes.
        # See docs/pipeline-rescan-idempotency-plan.md.
        #
        #   dump_system_specs() --> ""  ---------------> json.load fails --+
        #            |                                                    |
        #            v (path)                                             v
        #       load fresh --> ctx.specs (LIVE)              fall back to startup snapshot
        snapshot = ctx.specs
        fresh: dict = {}
        dump_path = dump_system_specs()
        if dump_path:
            try:
                with open(dump_path, "r", encoding="utf-8") as f:
                    fresh = json.load(f)
            except Exception as exc:
                log.warning(
                    "Phase 2: fresh spec file %s could not be parsed (%s)",
                    dump_path, exc,
                )

        if fresh:
            ctx.specs = fresh
            log.info("Phase 2: using fresh system scan")
            print_info(f"Full system specs temporarily saved to {dump_path}")
        elif snapshot:
            ctx.specs = snapshot
            log.warning("Phase 2: fresh scan unavailable -- using startup snapshot")
            print_info("Fresh scan unavailable -- using specs collected at startup.")
        else:
            ctx.specs = {}
            log.warning(
                "Phase 2: no system specs available "
                "(fresh scan and startup snapshot both empty)"
            )

        hw = extract_hardware_summary(ctx.specs) if ctx.specs else {}

        if hw:
            print()
            print_key_value("CPU", hw.get("cpu", "Unknown"))
            print_key_value("GPU", hw.get("gpu", "Unknown"))
            print_key_value("Driver", hw.get("gpu_driver", "Unknown"))
            print_key_value("RAM", f"{hw.get('ram_gb', 0)} GB @ {hw.get('ram_mhz', 0)} MHz")
            print_key_value("OS", hw.get("os", "Unknown"))
        return PhaseResult("completed", "System scan complete")
