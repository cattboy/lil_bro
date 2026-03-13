import sys
from colorama import init, Fore, Style

# Initialize colorama to support ANSI escape sequences on Windows
init(autoreset=True)

def print_header(title: str):
    """Prints a styled header for sections."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}=== {title} ==={Style.RESET_ALL}")

def print_success(message: str):
    """Prints a success message in green."""
    print(f"{Fore.GREEN}✓ {message}{Style.RESET_ALL}")

def print_warning(message: str):
    """Prints a warning message in yellow."""
    print(f"{Fore.YELLOW}⚠ {message}{Style.RESET_ALL}")

def print_error(message: str):
    """Prints an error message in red."""
    print(f"{Fore.RED}✗ {message}{Style.RESET_ALL}")

def print_info(message: str):
    """Prints an informational message."""
    print(f"{Fore.BLUE}ℹ {message}{Style.RESET_ALL}")

def print_step(message: str):
    """Prints a step indicator without a newline, useful for long-running ops."""
    print(f"{Fore.WHITE}{Style.DIM}• {message}... {Style.RESET_ALL}", end="", flush=True)

def print_step_done(success: bool = True):
    """Completes a step indicator line."""
    if success:
        print(f"{Fore.GREEN}Done!{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Failed!{Style.RESET_ALL}")

def prompt_approval(action_description: str) -> bool:
    """Prompts the user for yes/no approval for a specific action."""
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}? Requires Approval:{Style.RESET_ALL} {action_description}")
    while True:
        response = input(f"Proceed? [y/N]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no', '']:
            return False
        print(f"{Fore.RED}Invalid input. Please enter 'y' or 'n'.{Style.RESET_ALL}")
