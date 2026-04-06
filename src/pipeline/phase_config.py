"""Phase 4 — Esports Configuration Check: analyze, propose, approve."""

from src.pipeline.base import PipelineContext
from src.agent_tools.display import analyze_display
from src.agent_tools.game_mode import analyze_game_mode
from src.agent_tools.power_plan import analyze_power_plan
from src.agent_tools.xmp_check import analyze_xmp
from src.agent_tools.nvidia_profile import analyze_nvidia_profile
from src.agent_tools.rebar import analyze_rebar
from src.agent_tools.temp_audit import analyze_temp_folders
from src.agent_tools.mouse import check_polling_rate
from src.agent_tools.thermal_guidance import analyze_thermals
from src.utils.dump_parser import extract_hardware_summary
from src.llm.action_proposer import propose_actions
from src.utils.formatting import (
    print_header, print_info, print_warning, print_accent, print_dim,
    print_prompt, print_audit_summary, print_finding,
)
from src.utils.debug_logger import get_debug_logger
from src.pipeline.approval import run_approval_flow


class ConfigPhase:
    def run(self, ctx: PipelineContext) -> None:
        log = get_debug_logger()
        log.info("Phase 4: Apply Esports Configurations")
        print_header("Phase 4: Apply Esports Configurations")

        if not ctx.specs:
            print_warning("No system data available -- skipping configuration checks.")
            return

        findings = [
            analyze_display(ctx.specs),
            analyze_game_mode(ctx.specs),
            analyze_power_plan(ctx.specs),
            analyze_xmp(ctx.specs),
            analyze_rebar(ctx.specs),
            analyze_temp_folders(ctx.specs),
        ]

        nvidia_finding = analyze_nvidia_profile(ctx.specs)
        if nvidia_finding["status"] != "SKIPPED":
            findings.append(nvidia_finding)

        thermal_finding = analyze_thermals(
            ctx.peak_temps,
            cpu_peak=ctx.thermal.get_cpu_peak() if ctx.lhm_available else None,
            gpu_peak=ctx.thermal.get_gpu_peak() if ctx.lhm_available else None,
        )
        findings.append(thermal_finding)

        print()
        print_accent("Alright, wiggle your mouse for 2 seconds -- we'll measure the polling rate.")
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
        hardware = extract_hardware_summary(ctx.specs)
        if ctx.llm is not None:
            print_dim("Generating AI-powered recommendations...")
        else:
            print_dim("Generating recommendations...")
        proposals = propose_actions(hardware, findings, ctx.llm)

        run_approval_flow(proposals, ctx.specs)
