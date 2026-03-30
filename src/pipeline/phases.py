"""5-phase optimization pipeline orchestrator."""

import json

from src.bootstrapper import create_restore_point
from src.agent_tools.display import analyze_display
from src.agent_tools.game_mode import analyze_game_mode
from src.agent_tools.power_plan import analyze_power_plan
from src.agent_tools.xmp_check import analyze_xmp
from src.agent_tools.rebar import analyze_rebar
from src.agent_tools.temp_audit import analyze_temp_folders
from src.agent_tools.mouse import check_polling_rate
from src.agent_tools.thermal_guidance import analyze_thermals
from src.collectors.spec_dumper import dump_system_specs
from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.benchmarks.cinebench import BenchmarkRunner
from src.benchmarks.thermal_monitor import ThermalMonitor
from src.utils.dump_parser import extract_hardware_summary
from src.llm.action_proposer import propose_actions
from src.utils.formatting import (
    print_header, print_info, print_warning, print_error,
    print_success, print_accent, print_dim, print_prompt,
    print_key_value, print_audit_summary, print_finding,
    prompt_approval,
)
from src.utils.errors import LilBroError
from src.utils.action_logger import action_logger
from src.utils.debug_logger import get_debug_logger
from src.pipeline._state import get_llm
from src.pipeline.thermal_gate import thermal_safety_gate
from src.pipeline.approval import run_approval_flow


def run_optimization_pipeline():
    """Top-level pipeline entry. Manages LHM sidecar lifecycle."""
    action_logger.log_session_start()
    lhm = LHMSidecar()
    thermal = ThermalMonitor()

    try:
        _run_pipeline(lhm, thermal)
    finally:
        lhm.stop()
        action_logger.log_session_end()


def _run_pipeline(lhm: LHMSidecar, thermal: ThermalMonitor):
    """Executes all 5 phases sequentially."""

    log = get_debug_logger()

    # -- Phase 1: Bootstrapping & Safety --
    log.info("Phase 1: Bootstrapping & Safety")
    print_header("Phase 1: Bootstrapping & Safety")
    try:
        create_restore_point()
    except LilBroError as e:
        log.error("Restore point creation failed: %s", e)
        print_error(str(e))
        if not prompt_approval("Restore point creation failed. Continue anyway?"):
            return

    # -- Phase 2: Deep System Scan --
    log.info("Phase 2: Deep System Scan")
    print_header("Phase 2: Deep System Scan")

    lhm_available = lhm.start()
    if lhm_available:
        print_success("Thermal monitoring active on port 8085.")
    else:
        log.warning("LHM sidecar unavailable — continuing without thermal monitoring")
        print_info("Continuing without thermal monitoring -- Cinebench will still run.")

    dump_path = dump_system_specs()
    if dump_path:
        print_info(f"Full system specs saved to {dump_path}")
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs_preview = json.load(f)
            hw = extract_hardware_summary(specs_preview)
            print()
            print_key_value("CPU", hw.get('cpu', 'Unknown'))
            print_key_value("GPU", hw.get('gpu', 'Unknown'))
            print_key_value("Driver", hw.get('gpu_driver', 'Unknown'))
            print_key_value("RAM", f"{hw.get('ram_gb', 0)} GB @ {hw.get('ram_mhz', 0)} MHz")
            print_key_value("OS", hw.get('os', 'Unknown'))
        except Exception as exc:
            log.warning("Could not parse specs preview for display: %s", exc)

    # -- Phase 3: Baseline Benchmark --
    log.info("Phase 3: Baseline Benchmark")
    print_header("Phase 3: Baseline Benchmark")

    runner = BenchmarkRunner()
    benchmark_skipped = thermal_safety_gate(lhm_available)

    baseline: dict = {"status": "skipped", "message": "Skipped due to high idle temps"}
    peak_temps: dict[str, float] = {}

    if not benchmark_skipped:
        if lhm_available:
            thermal.start()
            print_info("Thermal monitoring active -- sampling temperatures during benchmark.")

        baseline = runner.run_benchmark(full_suite=False)

        if baseline.get("status") == "success":
            print_success("Baseline Benchmark Complete!")
            print_info(f"Scores: {baseline.get('scores', {})}")

        if lhm_available:
            thermal.stop()
            peak_temps = thermal.get_peak_temps()
            if peak_temps:
                cpu_peak = thermal.get_cpu_peak()
                gpu_peak = thermal.get_gpu_peak()
                parts = []
                if cpu_peak is not None:
                    parts.append(f"CPU: {cpu_peak:.1f}\u00b0C")
                if gpu_peak is not None:
                    parts.append(f"GPU: {gpu_peak:.1f}\u00b0C")
                if parts:
                    print_info(
                        f"Peak temps during benchmark: {', '.join(parts)} "
                        f"({thermal.sample_count} samples)"
                    )
            else:
                print_warning("Thermal monitor ran but captured no temperature data.")

    # -- Phase 4: Apply Esports Configurations --
    log.info("Phase 4: Apply Esports Configurations")
    print_header("Phase 4: Apply Esports Configurations")

    specs: dict = {}
    if dump_path:
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception as e:
            log.error("Could not load specs file %s: %s", dump_path, e)
            print_warning(f"Could not load specs file: {e}")

    if not specs:
        print_warning("No system data available -- skipping configuration checks.")
    else:
        findings = [
            analyze_display(specs),
            analyze_game_mode(specs),
            analyze_power_plan(specs),
            analyze_xmp(specs),
            analyze_rebar(specs),
            analyze_temp_folders(specs),
        ]

        thermal_finding = analyze_thermals(
            peak_temps,
            cpu_peak=thermal.get_cpu_peak() if lhm_available else None,
            gpu_peak=thermal.get_gpu_peak() if lhm_available else None,
        )
        findings.append(thermal_finding)

        print()
        print_accent("Alright, wiggle your mouse for 3 seconds -- we'll measure the polling rate.")
        print_prompt("Press Enter when you're ready... ")
        input()
        mouse_result = check_polling_rate()
        if mouse_result.get("status") == "WARNING":
            findings.append({
                "check": "mouse_polling",
                "status": "WARNING",
                "current_hz": mouse_result.get("current_hz", 0),
                "message": mouse_result.get("message", ""),
                "can_auto_fix": False,
            })

        print()
        warnings = [f for f in findings if f["status"] == "WARNING"]
        oks      = [f for f in findings if f["status"] == "OK"]
        unknowns = [f for f in findings if f["status"] not in ("OK", "WARNING")]
        print_audit_summary(len(oks), len(warnings), len(unknowns))
        print()
        for finding in findings:
            print_finding(finding["check"], finding["message"], finding["status"])

        print()
        hardware = extract_hardware_summary(specs)
        llm = get_llm()
        if llm is not None:
            print_dim("Generating AI-powered recommendations...")
        else:
            print_dim("Generating recommendations...")
        proposals = propose_actions(hardware, findings, llm)

        run_approval_flow(proposals, specs)

    # -- Phase 5: Final Verification Benchmark --
    log.info("Phase 5: Final Verification Benchmark")
    print_header("Phase 5: Final Verification Benchmark")

    final_skipped = thermal_safety_gate(
        lhm_available,
        skip_message="Skipping final benchmark.",
        approval_prompt="Temperatures are elevated. Run the final benchmark anyway?",
    )

    if not final_skipped:
        if lhm_available:
            thermal.start()

        final = runner.run_benchmark(full_suite=True)

        if lhm_available:
            thermal.stop()

        if final.get("status") == "success":
            print_success("Final Benchmark Complete!")
            print_info(f"After:  {final.get('scores', {})}")
            print_info(f"Before: {baseline.get('scores', {})}")
    else:
        print_info("Final benchmark was skipped -- no comparison available.")

    print_header("Optimization Pipeline Complete")
