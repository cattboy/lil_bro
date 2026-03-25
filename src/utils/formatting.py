import shutil
import sys
from colorama import init, Fore, Style

# Initialize colorama to support ANSI escape sequences on Windows
init(autoreset=True)

# Detect non-UTF-8 terminals (Windows CMD CP437, piped stdout, frozen builds).
# When True, icon-bearing functions use ASCII fallbacks instead of Unicode symbols.
_UNICODE_SAFE = getattr(sys.stdout, 'encoding', 'utf-8') not in ('utf-8', 'utf-8-sig')


def print_header(title: str):
    """Prints a styled header for sections."""
    print(f"\n{Fore.CYAN}{Style.BRIGHT}== {title} =={Style.RESET_ALL}")

def print_success(message: str):
    """Prints a success message in green."""
    icon = "OK" if _UNICODE_SAFE else "\u2713"
    print(f"{Fore.GREEN}{icon} {message}{Style.RESET_ALL}")

def print_warning(message: str):
    """Prints a warning message in yellow."""
    icon = "WARN" if _UNICODE_SAFE else "\u26a0"
    print(f"{Fore.YELLOW}{icon} {message}{Style.RESET_ALL}")

def print_error(message: str):
    """Prints an error message in red."""
    icon = "FAIL" if _UNICODE_SAFE else "\u2717"
    print(f"{Fore.RED}{icon} {message}{Style.RESET_ALL}")

def print_info(message: str):
    """Prints an informational message."""
    icon = "INFO" if _UNICODE_SAFE else "\u2139"
    print(f"{Fore.BLUE}{icon} {message}{Style.RESET_ALL}")

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
    print(f"{Fore.CYAN}> {message}{Style.RESET_ALL}", end="", flush=True)

def print_key_value(label: str, value: str, value_color=Fore.CYAN):
    """Prints a label: value pair with a dim label and colored value."""
    padded = f"{label}:"
    print(f"  {Style.DIM}{padded:<8}{Style.RESET_ALL}{value_color}{value}{Style.RESET_ALL}")

def print_section_divider(label: str = None):
    """Prints a terminal-width divider line with an optional centered label."""
    cols = max(20, shutil.get_terminal_size(fallback=(80, 24)).columns)
    dash = "-" if _UNICODE_SAFE else "\u2500"
    if label:
        side = (cols - len(label) - 2) // 2
        line = f"{dash * side} {label} {dash * (cols - side - len(label) - 2)}"
    else:
        line = dash * cols
    print(f"{Style.DIM}{line}{Style.RESET_ALL}")

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
    print(f"    {Fore.WHITE}{explanation}{Style.RESET_ALL}")
    print(f"    {Style.DIM}Fix: {action}  {fix_tag}{Style.RESET_ALL}")

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


def resize_console_window() -> None:
    """Resize the console window to 80% of the primary screen, centered.

    Skips resize when running inside Windows Terminal (which manages its
    own window layout) to avoid interfering with focus and input handling.
    """
    try:
        import ctypes
        import os

        # Windows Terminal manages its own window — resizing the pseudo-console
        # HWND can steal keyboard focus and break input().
        if os.environ.get("WT_SESSION"):
            return

        kernel32 = ctypes.windll.kernel32
        user32   = ctypes.windll.user32

        hwnd = kernel32.GetConsoleWindow()
        if not hwnd:
            return

        screen_w = user32.GetSystemMetrics(0)   # SM_CXSCREEN
        screen_h = user32.GetSystemMetrics(1)   # SM_CYSCREEN

        win_w = int(screen_w * 0.8)
        win_h = int(screen_h * 0.8)
        x     = (screen_w - win_w) // 2
        y     = (screen_h - win_h) // 2

        # Only de-maximize if actually maximized — unconditional SW_RESTORE
        # triggers WM_SIZE messages that can disrupt the console input state.
        if user32.IsZoomed(hwnd):
            user32.ShowWindow(hwnd, 9)   # SW_RESTORE

        # SWP_NOACTIVATE prevents SetWindowPos from triggering focus/activation
        # changes that steal keyboard input from the console.
        SWP_NOZORDER   = 0x0004
        SWP_NOACTIVATE = 0x0010
        user32.SetWindowPos(hwnd, None, x, y, win_w, win_h,
                            SWP_NOZORDER | SWP_NOACTIVATE)

        # Re-acquire keyboard focus after the position change.
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
