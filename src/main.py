import multiprocessing
import sys
import json
from colorama import Fore, Style

from src.bootstrapper import check_admin, create_restore_point
from src.agent_tools.display import analyze_display
from src.agent_tools.game_mode import analyze_game_mode
from src.agent_tools.power_plan import (
    analyze_power_plan,
    list_available_plans,
    set_active_plan,
    create_high_performance_plan,
    _PERF_GUIDS,
)
from src.agent_tools.xmp_check import analyze_xmp
from src.agent_tools.rebar import analyze_rebar
from src.agent_tools.temp_audit import analyze_temp_folders, clean_temp_folders
from src.agent_tools.mouse import check_polling_rate
from src.agent_tools.display_setter import find_best_mode, apply_display_mode
from src.collectors.spec_dumper import dump_system_specs
from src.collectors.sub.monitor_dumper import get_all_displays
from src.benchmarks.cinebench import BenchmarkRunner
from src.benchmarks.thermal_monitor import ThermalMonitor, fetch_snapshot
from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.agent_tools.thermal_guidance import analyze_thermals, check_idle_thermals
from src.utils.dump_parser import extract_hardware_summary
from src.llm.model_loader import load_model, get_model_status
from src.llm.action_proposer import propose_actions
from src.utils.formatting import (
    print_header, print_info, print_warning, print_error, print_success, prompt_approval,
    print_dim, print_accent, print_prompt, print_audit_summary, print_finding, print_proposal,
)
from src.utils.errors import LilBroError, AdminRequiredError
from src.utils.progress_bar import AnimatedProgressBar

# Module-level LLM instance — loaded once via "Setup AI Model", reused across runs.
_llm = None


def print_banner():
    banner = f"""{Fore.MAGENTA}{Style.BRIGHT}
   _   _    __  _           ___
 | | (_)  / / | |__   _ __ / _ \\
 | | | | / /  | '_ \\ | '__| | | |
 | | | |/ /   | |_) || |  | |_| |
 |_| |_/_/    |_.__/ |_|   \\___/
{Style.RESET_ALL}"""
    print(banner)
    print_accent("  Your Local AI PC Optimization Agent")
    print_dim("  Privacy Guarantee: 100% Offline Analysis. No data leaves your machine.\n")


# ── Menu ──────────────────────────────────────────────────────────────────────

def menu_loop():
    while True:
        print_header("Main Menu")

        if _llm is not None:
            ai_label = f"{Fore.GREEN}ready{Style.RESET_ALL}"
        else:
            ai_label = f"{Fore.YELLOW}not loaded{Style.RESET_ALL}"

        print(f"  {Fore.CYAN}1.{Style.RESET_ALL} Run Full Esports Optimization Pipeline")
        print(f"  {Fore.CYAN}2.{Style.RESET_ALL} Setup AI Model ({ai_label})")
        print(f"  {Fore.CYAN}3.{Style.RESET_ALL} Exit")

        print()
        print_prompt("Select an option [1-3]: ")
        choice = input().strip()

        if choice == '1':
            run_optimization_pipeline()
        elif choice == '2':
            setup_ai_model()
        elif choice == '3':
            print_info("shutting down, stay sweaty lil_bro.")
            sys.exit(0)
        else:
            print_error("Invalid choice. Try again.")


def setup_ai_model():
    """Interactive AI model management — shows status, offers download, loads model."""
    global _llm

    print_header("AI Model Setup")

    status = get_model_status()

    # ── Check toolchain ──────────────────────────────────────────────────
    if status["llama_installed"]:
        print_success("llama-cpp-python installed")
    else:
        print_warning("llama-cpp-python is not installed")
        print_info("Install with:  uv pip install llama-cpp-python")
        print_info(
            "\nThe optimization pipeline works without it — "
            "you'll get standard recommendations instead of AI-generated ones.\n"
        )
        return

    # ── Check model file ─────────────────────────────────────────────────
    if status["model_downloaded"]:
        print_success(f"Model downloaded: {status['model_path']}")
    else:
        print_info(f"Model not yet downloaded")
        print_info(f"Expected path: {status['model_path']}")

    # ── Already loaded? ──────────────────────────────────────────────────
    if _llm is not None:
        print_success("Model loaded and ready")
        print_info("\nNothing to do — AI model is already set up.")
        return

    # ── Load (handles download prompt internally if needed) ──────────────
    print()
    _llm = load_model()

    if _llm is not None:
        print_success("\nAI model is ready. The pipeline will use AI-powered explanations.")
    else:
        print_info(
            "\nThe pipeline works without the AI model — "
            "you'll get standard recommendations."
        )


# ── Phase 4 helpers ───────────────────────────────────────────────────────────

def _display_proposals(proposals: list[dict]) -> list[tuple[int, dict]]:
    """
    Prints the numbered proposal list. Returns only auto-fixable proposals
    as [(number, proposal), ...] so the caller knows which numbers to offer.
    """
    auto_fixable: list[tuple[int, dict]] = []
    num = 0

    for proposal in proposals:
        can_fix = proposal.get("can_auto_fix", False)
        num += 1
        print_proposal(
            num=num,
            severity=proposal.get("severity", "MEDIUM"),
            title=proposal.get("finding", "").replace("_", " ").title(),
            explanation=proposal.get("explanation", ""),
            action=proposal.get("proposed_action", ""),
            can_auto_fix=can_fix,
        )
        if can_fix:
            auto_fixable.append((num, proposal))

    return auto_fixable


def _parse_selection(raw: str, max_num: int) -> list[int] | None:
    """
    Parses the user's batch selection string.
    Returns a list of 1-based integers, an empty list for "skip",
    or None if input is invalid.
    """
    raw = raw.strip().lower()
    if raw in ("skip", "s", ""):
        return []
    if raw == "all":
        return list(range(1, max_num + 1))
    try:
        nums = [int(t) for t in raw.split()]
        if all(1 <= n <= max_num for n in nums):
            return nums
    except ValueError:
        pass
    return None


def _execute_fix(check: str, specs: dict) -> bool:
    """
    Executes the auto-fix for a given check without re-prompting the user.
    Approval was already obtained at the batch-selection step.
    Returns True on success.
    """
    if check == "display":
        try:
            devices = get_all_displays()
            device = devices[0] if devices else "\\\\.\\DISPLAY1"
            mode = find_best_mode(device, target_hz=None, require_same_resolution=True)
            if mode is None:
                print_error("[display] No suitable mode found — nothing changed.")
                return False
            ok, msg = apply_display_mode(device, mode, persist=True, dry_run=True)
            if not ok:
                print_error(f"[display] Validation failed: {msg}")
                return False
            ok, msg = apply_display_mode(device, mode, persist=True, dry_run=False)
            if ok:
                print_success(
                    f"[display] Refresh rate set to {mode.dmDisplayFrequency}Hz "
                    f"({mode.dmPelsWidth}x{mode.dmPelsHeight}). {msg}"
                )
            else:
                print_error(f"[display] Apply failed: {msg}")
            return ok
        except Exception as e:
            print_error(f"[display] Error: {e}")
            return False

    elif check == "power_plan":
        try:
            plans = list_available_plans()
            target = next((p for p in plans if p[0] in _PERF_GUIDS), None)
            if not target:
                target = next(
                    (p for p in plans if "performance" in p[1].lower()), None
                )
            if target:
                guid, name = target
            else:
                guid, name = create_high_performance_plan()
            set_active_plan(guid)
            print_success(f"[power_plan] Switched to '{name}'.")
            return True
        except Exception as e:
            print_error(f"[power_plan] Failed: {e}")
            return False

    elif check == "temp_folders":
        details = specs.get("TempFolders", {}).get("details", {})
        try:
            clean_temp_folders(details)
            return True
        except Exception as e:
            print_error(f"[temp_folders] Cleanup failed: {e}")
            return False

    elif check == "game_mode":
        from src.agent_tools.game_mode import set_game_mode
        try:
            set_game_mode(enabled=True)
            print_success("[game_mode] Game Mode enabled.")
            return True
        except Exception as e:
            print_error(f"[game_mode] Failed: {e}")
            return False

    return False  # check not auto-fixable


def _run_approval_flow(proposals: list[dict], specs: dict) -> None:
    """
    Renders the numbered proposal list, collects batch selection,
    and executes approved auto-fixable actions.
    """
    if not proposals:
        print_success("No configuration issues found — your setup looks good!")
        return

    auto_fixable = _display_proposals(proposals)

    if not auto_fixable:
        print_info(
            "\nAll findings require manual BIOS/driver changes — "
            "see the instructions above."
        )
        return

    total = len(proposals)
    print()
    print_prompt(f"Apply changes? Enter numbers (e.g. \"1 3\"), \"all\", or \"skip\": ")

    while True:
        raw = input().strip()
        selection = _parse_selection(raw, total)
        if selection is not None:
            break
        print_error("Invalid input.")
        print_prompt(f"Enter numbers 1–{total}, \"all\", or \"skip\": ")

    if not selection:
        print_info("No changes applied.")
        return

    # Map selected numbers to proposals
    selected_proposals = {n: p for n, p in auto_fixable if n in selection}
    # Also include manual proposals if user selected them (informational)
    for n in selection:
        proposal = proposals[n - 1]
        if not proposal.get("can_auto_fix") and n not in selected_proposals:
            print_info(
                f"[{proposal.get('finding')}] Manual action required: "
                f"{proposal.get('proposed_action')}"
            )

    print()
    bar = AnimatedProgressBar(total=len(selected_proposals), label="Applying fixes")
    bar.start()

    for i, (_n, proposal) in enumerate(sorted(selected_proposals.items()), 1):
        check = proposal.get("finding", "")
        bar.update(i, f"Fixing {check.replace('_', ' ')}...")
        _execute_fix(check, specs)

    bar.finish()

    # Partial failure notice
    print_info(
        "\nIf anything looks wrong, a System Restore Point was created at startup. "
        "Open 'Create a restore point' in Windows to roll back."
    )


# ── Pipeline ──────────────────────────────────────────────────────────────────

def run_optimization_pipeline():
    lhm = LHMSidecar()
    thermal = ThermalMonitor()

    try:
        _run_pipeline(lhm, thermal)
    finally:
        # Always clean up the sidecar, even on error/Ctrl+C
        lhm.stop()


def _run_pipeline(lhm: LHMSidecar, thermal: ThermalMonitor):
    print_header("Phase 1: Bootstrapping & Safety")
    try:
        create_restore_point()
    except LilBroError as e:
        print_error(str(e))
        if not prompt_approval("Restore point creation failed. Continue anyway?"):
            return

    print_header("Phase 2: Deep System Scan")

    # Launch LibreHardwareMonitor sidecar for thermal data
    lhm_available = lhm.start()
    if lhm_available:
        print_success("Thermal monitoring active on port 8085.")
    else:
        print_info("Continuing without thermal monitoring — Cinebench will still run.")

    dump_path = dump_system_specs()
    if dump_path:
        print_info(f"Full system specs saved to {dump_path}")

        # Show key hardware info to the user
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs_preview = json.load(f)
            hw = extract_hardware_summary(specs_preview)

            print()
            print(f"  {Style.DIM}CPU:   {Style.RESET_ALL}{Fore.CYAN}{hw.get('cpu', 'Unknown')}{Style.RESET_ALL}")
            print(f"  {Style.DIM}GPU:   {Style.RESET_ALL}{Fore.CYAN}{hw.get('gpu', 'Unknown')}{Style.RESET_ALL}")
            print(f"  {Style.DIM}Driver:{Style.RESET_ALL}{Fore.CYAN}{hw.get('gpu_driver', 'Unknown')}{Style.RESET_ALL}")
            print(f"  {Style.DIM}RAM:   {Style.RESET_ALL}{Fore.CYAN}{hw.get('ram_gb', 0)} GB @ {hw.get('ram_mhz', 0)} MHz{Style.RESET_ALL}")
            print(f"  {Style.DIM}OS:    {Style.RESET_ALL}{Fore.CYAN}{hw.get('os', 'Unknown')}{Style.RESET_ALL}")
        except Exception:
            pass  # Non-critical — don't block pipeline over a display error

    print_header("Phase 3: Baseline Benchmark")

    runner = BenchmarkRunner()

    # Pre-benchmark thermal safety gate
    benchmark_skipped = False
    if lhm_available:
        print_info("Checking idle temperatures before benchmark...")
        idle_temps = fetch_snapshot()
        idle_check = check_idle_thermals(idle_temps)

        if idle_check["safe"]:
            print_success(idle_check["message"])
        else:
            print_warning(idle_check["message"])
            if not prompt_approval("Temperatures are elevated. Run the benchmark anyway?"):
                print_info("Skipping benchmark — let your PC cool down and try again.")
                benchmark_skipped = True

    # Run benchmark with thermal monitoring (unless skipped)
    baseline: dict = {"status": "skipped", "message": "Skipped due to high idle temps"}
    peak_temps: dict[str, float] = {}

    if not benchmark_skipped:
        if lhm_available:
            thermal.start()
            print_info("Thermal monitoring active — sampling temperatures during benchmark.")

        baseline = runner.run_benchmark(full_suite=False)

        if baseline.get("status") == "success":
            print_success("Baseline Benchmark Complete!")
            print_info(f"Scores: {baseline.get('scores', {})}")

        # Stop thermal polling and capture peak temps
        if lhm_available:
            thermal.stop()
            peak_temps = thermal.get_peak_temps()
            if peak_temps:
                cpu_peak = thermal.get_cpu_peak()
                gpu_peak = thermal.get_gpu_peak()
                parts = []
                if cpu_peak is not None:
                    parts.append(f"CPU: {cpu_peak:.1f}°C")
                if gpu_peak is not None:
                    parts.append(f"GPU: {gpu_peak:.1f}°C")
                if parts:
                    print_info(
                        f"Peak temps during benchmark: {', '.join(parts)} "
                        f"({thermal.sample_count} samples)"
                    )
            else:
                print_warning("Thermal monitor ran but captured no temperature data.")

    print_header("Phase 4: Apply Esports Configurations")

    specs: dict = {}
    if dump_path:
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception as e:
            print_warning(f"Could not load specs file: {e}")

    if not specs:
        print_warning("No system data available — skipping configuration checks.")
    else:
        # Run all pure analyzers
        findings = [
            analyze_display(specs),
            analyze_game_mode(specs),
            analyze_power_plan(specs),
            analyze_xmp(specs),
            analyze_rebar(specs),
            analyze_temp_folders(specs),
        ]

        # Thermal guidance (from benchmark peak temps)
        thermal_finding = analyze_thermals(
            peak_temps,
            cpu_peak=thermal.get_cpu_peak() if lhm_available else None,
            gpu_peak=thermal.get_gpu_peak() if lhm_available else None,
        )
        findings.append(thermal_finding)

        # Mouse: live check (not spec-fed) — normalize into finding format
        print()
        print_accent("Alright, wiggle your mouse for 3 seconds — we'll measure the polling rate.")
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

        # Print audit summary
        print()
        warnings = [f for f in findings if f["status"] == "WARNING"]
        oks      = [f for f in findings if f["status"] == "OK"]
        unknowns = [f for f in findings if f["status"] not in ("OK", "WARNING")]
        print_audit_summary(len(oks), len(warnings), len(unknowns))
        print()
        for finding in findings:
            print_finding(finding["check"], finding["message"], finding["status"])

        # Generate proposals — AI-powered if model loaded, standard otherwise
        print()
        hardware = extract_hardware_summary(specs)
        if _llm is not None:
            print_dim("Generating AI-powered recommendations...")
        else:
            print_dim("Generating recommendations...")
        proposals = propose_actions(hardware, findings, _llm)

        _run_approval_flow(proposals, specs)

    print_header("Phase 5: Final Verification Benchmark")

    # Pre-benchmark thermal gate (same pattern as Phase 3)
    final_skipped = False
    if lhm_available:
        print_info("Checking temps before final benchmark...")
        idle_temps_final = fetch_snapshot()
        idle_check_final = check_idle_thermals(idle_temps_final)

        if idle_check_final["safe"]:
            print_success(idle_check_final["message"])
        else:
            print_warning(idle_check_final["message"])
            if not prompt_approval("Temperatures are elevated. Run the final benchmark anyway?"):
                print_info("Skipping final benchmark.")
                final_skipped = True

    if not final_skipped:
        # Restart thermal monitoring for the final benchmark
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
        print_info("Final benchmark was skipped — no comparison available.")

    print_header("Optimization Pipeline Complete")


def main():
    multiprocessing.freeze_support()  # Required for PyInstaller onefile + multiprocessing.Pool
    try:
        # Verify file integrity in frozen builds (no-op in dev)
        from src.utils.integrity import verify_integrity
        verify_integrity()

        print_banner()

        print_info("Checking system privileges...")
        try:
            check_admin()
        except AdminRequiredError as e:
            print_error(str(e))
            print_warning("Some features (like Restore Point Creation) will fail without Admin rights.")
            print()

        menu_loop()

    except KeyboardInterrupt:
        print_accent("\nCtrl+C detected. Exiting...")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
