import sys
from colorama import init, Fore, Style

# Initialize colorama to support ANSI escape sequences on Windows
init(autoreset=True)

def print_header(title: str):
    """Prints a styled header for sections."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}== {title} =={Style.RESET_ALL}")

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

def print_dim(message: str):
    """Prints muted secondary text."""
    print(f"{Style.DIM}{message}{Style.RESET_ALL}")

def print_accent(message: str):
    """Prints accent-colored (cyan) text for highlights and subtitles."""
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}")

def print_prompt(message: str):
    """Prints an input prompt without a newline (cursor stays on the same line)."""
    print(f"{Fore.CYAN}{message}{Style.RESET_ALL}", end="", flush=True)

def print_audit_summary(ok: int, warnings: int, unknowns: int):
    """Prints a compound-colored audit result line."""
    print(
        f"{Style.DIM}Audit complete:{Style.RESET_ALL}  "
        f"{Fore.GREEN}{ok} OK{Style.RESET_ALL}"
        f"{Style.DIM}  —  {Style.RESET_ALL}"
        f"{Fore.YELLOW}{warnings} need attention{Style.RESET_ALL}"
        f"{Style.DIM}  —  {unknowns} unknown{Style.RESET_ALL}"
    )

def print_finding(label: str, message: str, status: str):
    """Prints a finding with a status-colored bracket label and plain message."""
    status_color = {
        "OK":      Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR":   Fore.RED,
    }.get(status, Fore.WHITE)
    print(f"  {status_color}[{label.upper()}]{Style.RESET_ALL} {message}")

def print_proposal(num: int, severity: str, title: str,
                   explanation: str, action: str, can_auto_fix: bool):
    """Prints a full proposal block with severity-colored bold header."""
    severity_color = {
        "HIGH":   Fore.RED,
        "MEDIUM": Fore.YELLOW,
        "LOW":    Fore.CYAN,
    }.get(severity, Fore.WHITE)
    fix_tag = (
        f"{Fore.GREEN}[AUTO]{Style.RESET_ALL}"
        if can_auto_fix
        else f"{Style.DIM}[MANUAL]{Style.RESET_ALL}"
    )
    print(f"\n{severity_color}{Style.BRIGHT}[{num}] {severity} — {title}{Style.RESET_ALL}")
    print(f"    {Style.DIM}{explanation}{Style.RESET_ALL}")
    print(f"    Fix: {action}  {fix_tag}")

def prompt_confirm(question: str) -> bool:
    """Branded yes/no prompt for non-system decisions (e.g. model download)."""
    print(f"{Fore.MAGENTA}{question} [y/N]: {Style.RESET_ALL}", end="", flush=True)
    return input().strip().lower() in ("y", "yes")

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
