import sys
import json
import colorama
from colorama import Fore, Style

from src.bootstrapper import check_admin, create_restore_point
from src.agent_tools.display import analyze_display
from src.agent_tools.game_mode import analyze_game_mode
from src.agent_tools.power_plan import analyze_power_plan, check_power_plan
from src.agent_tools.xmp_check import analyze_xmp
from src.agent_tools.rebar import analyze_rebar
from src.agent_tools.temp_audit import analyze_temp_folders, scan_temp_folders, clean_temp_folders
from src.agent_tools.mouse import check_polling_rate
from src.collectors.spec_dumper import dump_system_specs
from src.benchmarks.cinebench import CinebenchOrchestrator
from src.utils.formatting import print_header, print_info, print_warning, print_error, print_success, prompt_approval
from src.utils.errors import LilBroError, AdminRequiredError

def print_banner():
    banner = f"""{Fore.MAGENTA}{Style.BRIGHT}
  _   _    __  _                  ___  
 | | (_)  / / | |__   _ __  ___  / _ \ 
 | | | | / /  | '_ \ | '__|/ _ \| | | |
 | | | |/ /   | |_) || |  | (_) | |_| |
 |_| |_/_/    |_.__/ |_|   \___/ \___/ 
                                       
  Your Local AI PC Optimization Agent
{Style.RESET_ALL}"""
    print(banner)
    print_info("Privacy Guarantee: 100% Offline Analysis. No data leaves your machine.\n")

def menu_loop():
    while True:
        print_header("Main Menu")
        print("1. Run Full Esports Optimization Pipeline (Workflow-First)")
        print("2. Exit")
        
        choice = input(f"\n{Fore.CYAN}Select an option [1-2]: {Style.RESET_ALL}").strip()
        
        if choice == '1':
            run_optimization_pipeline()
        elif choice == '2':
            print_info("shutting down, stay sweaty lil_bro.")
            sys.exit(0)
        else:
            print_error("Invalid choice. Try again.")

def run_optimization_pipeline():
    print_header("Phase 1: Bootstrapping & Safety")
    try:
        create_restore_point()
    except LilBroError as e:
        print_error(str(e))
        if not prompt_approval("Restore point creation failed. Continue anyway?"):
            return

    print_header("Phase 2: Deep System Scan")
    dump_path = dump_system_specs()
    if dump_path:
        print_info(f"Full system specs saved to {dump_path}")

    print_header("Phase 3: Baseline Benchmark")
    cb = CinebenchOrchestrator()
    baseline = cb.run_benchmark(run_all=False)
    if baseline.get("status") == "success":
        print_success("Baseline Benchmark Complete!")
        print_info(f"Scores: {baseline.get('scores', {})}")
        
    print_header("Phase 4: Apply Esports Configurations")

    # Load specs collected in Phase 2 and run all pure analyzers
    findings = []
    specs = {}
    if dump_path:
        try:
            with open(dump_path, "r", encoding="utf-8") as f:
                specs = json.load(f)
        except Exception as e:
            print_warning(f"Could not load specs file: {e}")

    if specs:
        findings = [
            analyze_display(specs),
            analyze_game_mode(specs),
            analyze_power_plan(specs),
            analyze_xmp(specs),
            analyze_rebar(specs),
            analyze_temp_folders(specs),
        ]

        # Print audit summary
        print()
        warnings = [f for f in findings if f["status"] == "WARNING"]
        oks      = [f for f in findings if f["status"] == "OK"]
        unknowns = [f for f in findings if f["status"] not in ("OK", "WARNING")]
        print_info(f"Audit complete: {len(oks)} OK, {len(warnings)} need attention, {len(unknowns)} unknown")
        print()
        for finding in findings:
            label = f"  [{finding['check'].upper()}]"
            if finding["status"] == "OK":
                print_success(f"{label} {finding['message']}")
            elif finding["status"] == "WARNING":
                print_warning(f"{label} {finding['message']}")
            else:
                print_error(f"{label} {finding['message']}")
        print()

    # Apply fixes for actionable findings
    for finding in findings:
        if finding["status"] != "WARNING" or not finding.get("can_auto_fix"):
            continue
        check = finding["check"]

        if check == "power_plan":
            check_power_plan()

        elif check == "display":
            print_info("[display] Auto-fix: open Windows Display Settings and set the refresh rate to the maximum supported.")

        elif check == "temp_folders":
            total_bytes = specs.get("TempFolders", {}).get("total_bytes", 0)
            details     = specs.get("TempFolders", {}).get("details", {})
            MB = total_bytes / (1024 * 1024)
            if prompt_approval(f"Clean {MB:.2f} MB of temporary files?"):
                clean_temp_folders(details)

    # Mouse polling rate — live check, not spec-fed
    print()
    print_warning("PREPARE TO WIGGLE THE MOUSE FOR 3 SECONDS...")
    input(f"{Fore.CYAN}Press Enter to begin tracking...{Style.RESET_ALL}")
    check_polling_rate()

    print_header("Phase 5: Final Verification Benchmark")
    final = cb.run_benchmark(run_all=True)
    if final.get("status") == "success":
        print_success("Final Benchmark Complete!")
        print_info(f"Scores: {final.get('scores', {})}")
        print_info(f"Scores: {baseline.get('scores', {})}")
        
    print_header("Optimization Pipeline Complete")

def main():
    try:
        colorama.init(autoreset=True)
        print_banner()
        
        # We need admin for the safety net and reading deep system settings
        print_info("Checking system privileges...")
        try:
            check_admin()
        except AdminRequiredError as e:
            print_error(str(e))
            # Continue for PoC so user can still test non-admin parts
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
