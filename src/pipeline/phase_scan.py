"""Phase 2 — Deep System Scan: LHM start, spec dump, hardware preview."""

import json

from src.pipeline.base import PipelineContext, PhaseResult
from src.collectors.spec_dumper import dump_system_specs
from src.utils.dump_parser import extract_hardware_summary
from src.utils.formatting import (
    print_header, print_success, print_info, print_key_value,
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

        dump_path = dump_system_specs()
        if dump_path:
            print_info(f"Full system specs temporarily saved to {dump_path}")
            try:
                with open(dump_path, "r", encoding="utf-8") as f:
                    ctx.specs = json.load(f)
                hw = extract_hardware_summary(ctx.specs)
                print()
                print_key_value("CPU", hw.get("cpu", "Unknown"))
                print_key_value("GPU", hw.get("gpu", "Unknown"))
                print_key_value("Driver", hw.get("gpu_driver", "Unknown"))
                print_key_value("RAM", f"{hw.get('ram_gb', 0)} GB @ {hw.get('ram_mhz', 0)} MHz")
                print_key_value("OS", hw.get("os", "Unknown"))
            except Exception as exc:
                log.warning("Could not parse specs preview for display: %s", exc)
        return PhaseResult("completed", "System scan complete")
