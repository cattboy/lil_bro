import sys
import colorama
from colorama import Fore, Style

from src.bootstrapper import check_admin, create_restore_point
from src.agent_tools.display import check_refresh_rate
from src.agent_tools.mouse import check_polling_rate
from src.agent_tools.temp_audit import scan_temp_folders, clean_temp_folders
from src.agent_tools.game_mode import check_game_mode
from src.agent_tools.power_plan import check_power_plan
from src.agent_tools.xmp_check import check_xmp_status
from src.agent_tools.rebar import check_rebar
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
    print_info("Running configuration audits. Changes will be logged to C:\\Temp\\lil_bro_actions.log")
    
    print()
    check_refresh_rate()
    print()
    check_game_mode()
    print()
    check_power_plan()
    print()
    check_xmp_status()
    print()
    check_rebar()
    print()
    
    # Debloat
    results = scan_temp_folders()
    if results['total_bytes'] > 0:
        MB = results['total_bytes'] / (1024*1024)
        print()
        if prompt_approval(f"Would you like me to clean {MB:.2f} MB of temp files?"):
            clean_temp_folders(results['details'])
            
    print()
    # print(f"{Fore.YELLOW}PREPARE TO WIGGLE THE MOUSE FOR 3 SECONDS...{Style.RESET_ALL}")
    # input("Press Enter to begin tracking...")
    # check_polling_rate() Add later

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
