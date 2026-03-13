import sys
import colorama
from colorama import Fore, Style

from src.bootstrapper import check_admin, create_restore_point
from src.scanners.display import check_refresh_rate
from src.scanners.mouse import check_polling_rate
from src.scanners.temp_audit import scan_temp_folders
from src.scanners.game_mode import check_game_mode
from src.scanners.power_plan import check_power_plan
from src.scanners.xmp_check import check_xmp_status
from src.utils.formatting import print_header, print_info, print_error, prompt_approval
from src.utils.errors import LilBroError, AdminRequiredError
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
        print("1. Run Configuration Check (Esports Check)")
        print("2. Run Speed Up My PC (Debloat & Benchmark)")
        print("3. Exit")
        
        choice = input(f"\n{Fore.CYAN}Select an option [1-3]: {Style.RESET_ALL}").strip()
        
        if choice == '1':
            run_esports_check()
        elif choice == '2':
            run_speed_up()
        elif choice == '3':
            print_info("shutting down, stay sweaty lil_bro.")
            sys.exit(0)
        else:
            print_error("Invalid choice. Try again.")

def run_esports_check():
    print_header("Starting Configuration Check")
    
    # 1. Display
    print()
    check_refresh_rate()
    
    # 2. Mouse Input
    print()
    # Briefly block UI with clear instructions
    print(f"{Fore.YELLOW}PREPARE TO WIGGLE THE MOUSE FOR 3 SECONDS...{Style.RESET_ALL}")
    input("Press Enter to begin tracking...")
    check_polling_rate()
    
    # 3. Game Mode
    print()
    check_game_mode()
    
    # 4. Power Plan
    print()
    check_power_plan()
    
    # 5. XMP/EXPO
    print()
    check_xmp_status()
    
    print_header("Configuration Check Complete")

def run_speed_up():
    print_header("Starting Speed Up Sequence")
    
    # 1. System Safety Create Restore Point
    try:
        if not prompt_approval("CREATE A SYSTEM RESTORE POINT first? (Highly Recommended), if you don't like what happens, just restore to this point and uninstall lil_bro."):
             print_warning("Proceeding AT YOUR OWN RISK without a restore point. YOU WERE WARNED MY GUY")
        else:
            create_restore_point()
    except LilBroError as e:
        print_error(str(e))
        if not prompt_approval("Restore point creation failed. Continue anyway?"):
            return
            
    # 2. Debloat Scan
    print()
    results = scan_temp_folders()
    
    if results['total_bytes'] > 0:
        MB = results['total_bytes'] / (1024*1024)
        print()
        if prompt_approval(f"Would you like me to clean {MB:.2f} MB of temp files?"):
            from src.scanners.temp_audit import clean_temp_folders
            clean_temp_folders(results['details'])
            
    print_header("Speed Up Sequence Complete")

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
