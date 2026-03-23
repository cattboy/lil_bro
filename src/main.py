import sys
import json
import colorama
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
from src.benchmarks.cinebench import CinebenchOrchestrator
from src.benchmarks.thermal_monitor import ThermalMonitor
from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.agent_tools.thermal_guidance import analyze_thermals
from src.utils.dump_parser import extract_hardware_summary
from src.llm.model_loader import load_model, get_model_status
from src.llm.action_proposer import propose_actions
from src.utils.formatting import (
    print_header, print_info, print_warning, print_error, print_success, prompt_approval,
)
from src.utils.errors import LilBroError, AdminRequiredError

# Module-level LLM instance — loaded once via "Setup AI Model", reused across runs.
_llm = None


def print_banner():
    banner = f"""{Fore.MAGENTA}{Style.BRIGHT}
  _   _    __  _                  ___
 | | (_)  / / | |__   _ __  ___  / _ \\
 | | | | / /  | '_ \\ | '__|/ _ \\| | | |
 | | | |/ /   | |_) || |  | (_) | |_| |
 |_| |_/_/    |_.__/ |_|   \\___/ \\___/

  Your Local AI PC Optimization Agent
{Style.RESET_ALL}"""
    print(banner)
    print_info("Privacy Guarantee: 100% Offline Analysis. No data leaves your machine.\n")


# ── Menu ──────────────────────────────────────────────────────────────────────

def menu_loop():
    while True:
        print_header("Main Menu")

        if _llm is not None:
            ai_label = f"{Fore.GREEN}ready{Style.RESET_ALL}"
        else:
            ai_label = f"{Fore.YELLOW}not loaded{Style.RESET_ALL}"

        print("1. Run Full Esports Optimization Pipeline")
        print(f"2. Setup AI Model ({ai_label})")
        print("3. Exit")

        choice = input(f"\n{Fore.CYAN}Select an option [1-3]: {Style.RESET_ALL}").strip()

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

    severity_color = {
        "HIGH":   Fore.RED,
        "MEDIUM": Fore.YELLOW,
        "LOW":    Fore.CYAN,
    }

    for proposal in proposals:
        can_fix = proposal.get("can_auto_fix", False)
        num += 1
        sev = proposal.get("severity", "MEDIUM")
        color = severity_color.get(sev, Fore.WHITE)

        fix_tag = (
            f"{Fore.GREEN}[AUTO]{Style.RESET_ALL}"
            if can_fix
            else f"{Fore.WHITE}[MANUAL]{Style.RESET_ALL}"
        )
        print(
            f"\n{color}{Style.BRIGHT}[{num}] {sev} — "
            f"{proposal.get('finding', '').replace('_', ' ').title()}{Style.RESET_ALL}"
        )
        print(f"    {proposal.get('explanation', '')}")
        print(f"    Fix: {proposal.get('proposed_action', '')}  {fix_tag}")

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
    print(
        f"\n{Fore.CYAN}Apply changes? "
        f"Enter numbers (e.g. \"1 3\"), \"all\", or \"skip\":{Style.RESET_ALL} ",
        end="",
    )

    while True:
        raw = input().strip()
        selection = _parse_selection(raw, total)
        if selection is not None:
            break
        print(
            f"{Fore.RED}Invalid input.{Style.RESET_ALL} "
            f"Enter numbers 1–{total}, \"all\", or \"skip\": ",
            end="",
        )

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
    for _n, proposal in sorted(selected_proposals.items()):
        check = proposal.get("finding", "")
        _execute_fix(check, specs)

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

    print_header("Phase 3: Baseline Benchmark")

    # Start thermal polling before benchmark (if LHM is running)
    if lhm_available:
        thermal.start()
        print_info("Thermal monitoring active — sampling temperatures during benchmark.")

    cb = CinebenchOrchestrator()
    baseline = cb.run_benchmark(run_all=False)
    if baseline.get("status") == "success":
        print_success("Baseline Benchmark Complete!")
        print_info(f"Scores: {baseline.get('scores', {})}")

    # Stop thermal polling and capture peak temps
    peak_temps: dict[str, float] = {}
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
                print_info(f"Peak temps during benchmark: {', '.join(parts)} ({thermal.sample_count} samples)")
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
        print_warning("PREPARE TO WIGGLE THE MOUSE FOR 3 SECONDS...")
        input(f"{Fore.CYAN}Press Enter to begin tracking...{Style.RESET_ALL}")
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
        print_info(
            f"Audit complete: {len(oks)} OK, {len(warnings)} need attention, "
            f"{len(unknowns)} unknown"
        )
        print()
        for finding in findings:
            label = f"  [{finding['check'].upper()}]"
            if finding["status"] == "OK":
                print_success(f"{label} {finding['message']}")
            elif finding["status"] == "WARNING":
                print_warning(f"{label} {finding['message']}")
            else:
                print_error(f"{label} {finding['message']}")

        # Generate proposals — AI-powered if model loaded, standard otherwise
        print()
        hardware = extract_hardware_summary(specs)
        if _llm is not None:
            print_info("Generating AI-powered recommendations...")
        else:
            print_info("Generating recommendations...")
        proposals = propose_actions(hardware, findings, _llm)

        _run_approval_flow(proposals, specs)

    print_header("Phase 5: Final Verification Benchmark")

    # Restart thermal monitoring for the final benchmark
    if lhm_available:
        thermal.start()

    final = cb.run_benchmark(run_all=True)

    if lhm_available:
        thermal.stop()

    if final.get("status") == "success":
        print_success("Final Benchmark Complete!")
        print_info(f"After:  {final.get('scores', {})}")
        print_info(f"Before: {baseline.get('scores', {})}")

    print_header("Optimization Pipeline Complete")


def main():
    try:
        colorama.init(autoreset=True)
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
        print(f"\n{Fore.CYAN}Ctrl+C detected. Exiting...{Style.RESET_ALL}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
