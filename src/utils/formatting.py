import shutil
import sys
from colorama import init, Fore, Style

# Initialize colorama to support ANSI escape sequences on Windows
init(autoreset=True)

# Detect non-UTF-8 terminals (Windows CMD CP437, piped stdout, frozen builds).
# When True, icon-bearing functions use ASCII fallbacks instead of Unicode symbols.
_ASCII_FALLBACK = getattr(sys.stdout, 'encoding', 'utf-8') not in ('utf-8', 'utf-8-sig')


from collections.abc import Callable

# --- Output sink + handler registry --------------------------------------
# CLI mode: all three are None → print()/input() are used (current behavior).
# GUI mode: bridge.install() swaps these at startup so output streams to the
# Qt panel and approval/confirm prompts open as modal dialogs.
#
# Late-lookup pattern: each consumer reads the module global at call time
# (not import time), so handler swaps reach already-imported callers — e.g.
# pipeline modules loaded before the GUI bridge installs its handlers.
_DEFAULT_SINK: Callable[[str], None] | None = None
_APPROVAL_HANDLER: Callable[[str], bool] | None = None
_CONFIRM_HANDLER: Callable[[str], bool] | None = None
_PAUSE_HANDLER: Callable[[str], None] | None = None
_BATCH_SELECTION_HANDLER: Callable[[list, int], list[int]] | None = None
_PAUSE_HANDLER: Callable[[str], None] | None = None
_BATCH_SELECTION_HANDLER: Callable[[list, int], list[int]] | None = None


def set_default_sink(sink: Callable[[str], None] | None) -> None:
    """Install (or clear) the default text sink for all print_* helpers."""
    global _DEFAULT_SINK
    _DEFAULT_SINK = sink


def set_approval_handler(handler: Callable[[str], bool] | None) -> None:
    """Install (or clear) the approval handler. ``None`` restores CLI input()."""
    global _APPROVAL_HANDLER
    _APPROVAL_HANDLER = handler


def set_confirm_handler(handler: Callable[[str], bool] | None) -> None:
    """Install (or clear) the confirm handler. ``None`` restores CLI input()."""
    global _CONFIRM_HANDLER
    _CONFIRM_HANDLER = handler


def set_pause_handler(handler: Callable[[str], None] | None) -> None:
    """Install (or clear) the pause handler. ``None`` restores CLI input()."""
    global _PAUSE_HANDLER
    _PAUSE_HANDLER = handler


def set_batch_selection_handler(
    handler: Callable[[list, int], list[int]] | None,
) -> None:
    """Install (or clear) the batch-selection handler. ``None`` restores CLI."""
    global _BATCH_SELECTION_HANDLER
    _BATCH_SELECTION_HANDLER = handler


def get_batch_selection_handler() -> Callable[[list, int], list[int]] | None:
    """Read the current batch-selection handler (None outside GUI mode)."""
    return _BATCH_SELECTION_HANDLER


def _emit(text: str, sink: Callable[[str], None] | None = None, end: str = "\n") -> None:
    """Route a formatted string. Per-call ``sink`` wins, else ``_DEFAULT_SINK``, else print()."""
    chosen = sink if sink is not None else _DEFAULT_SINK
    if chosen is not None:
        chosen(text + end)
    else:
        print(text, end=end, flush=(end == ""))


def print_header(title: str, output_sink: Callable[[str], None] | None = None):
    """Prints a styled header for sections."""
    _emit(f"\n{Fore.CYAN}{Style.BRIGHT}== {title} =={Style.RESET_ALL}", sink=output_sink)

def print_success(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints a success message in green."""
    icon = "OK" if _ASCII_FALLBACK else "✓"
    _emit(f"{Fore.GREEN}{icon} {message}{Style.RESET_ALL}", sink=output_sink)

def print_warning(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints a warning message in yellow."""
    icon = "WARN" if _ASCII_FALLBACK else "⚠"
    _emit(f"{Fore.YELLOW}{icon} {message}{Style.RESET_ALL}", sink=output_sink)

def print_error(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints an error message in red."""
    icon = "FAIL" if _ASCII_FALLBACK else "✗"
    _emit(f"{Fore.RED}{icon} {message}{Style.RESET_ALL}", sink=output_sink)

def print_info(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints an informational message."""
    icon = "INFO" if _ASCII_FALLBACK else "ℹ"
    _emit(f"{Fore.BLUE}{icon} {message}{Style.RESET_ALL}", sink=output_sink)

def print_step(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints a step indicator without a newline, useful for long-running ops."""
    _emit(f"{Fore.WHITE}{Style.DIM}• {message}... {Style.RESET_ALL}", sink=output_sink, end="")

def print_step_done(success: bool = True, output_sink: Callable[[str], None] | None = None):
    """Completes a step indicator line."""
    if success:
        _emit(f"{Fore.GREEN}Done!{Style.RESET_ALL}", sink=output_sink)
    else:
        _emit(f"{Fore.RED}Failed!{Style.RESET_ALL}", sink=output_sink)

def print_dim(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints muted secondary text."""
    _emit(f"{Style.DIM}{message}{Style.RESET_ALL}", sink=output_sink)

def print_accent(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints accent-colored (cyan) text for highlights and subtitles."""
    _emit(f"{Fore.CYAN}{message}{Style.RESET_ALL}", sink=output_sink)

def print_prompt(message: str, output_sink: Callable[[str], None] | None = None):
    """Prints an input prompt without a newline (cursor stays on the same line)."""
    _emit(f"{Fore.CYAN}> {message}{Style.RESET_ALL}", sink=output_sink, end="")

def print_key_value(label: str, value: str, value_color=Fore.CYAN,
                    output_sink: Callable[[str], None] | None = None):
    """Prints a label: value pair with a dim label and colored value."""
    padded = f"{label}:"
    _emit(f"  {Style.DIM}{padded:<8}{Style.RESET_ALL}{value_color}{value}{Style.RESET_ALL}",
          sink=output_sink)

def print_section_divider(label: str = None, output_sink: Callable[[str], None] | None = None):
    """Prints a terminal-width divider line with an optional centered label."""
    cols = max(20, shutil.get_terminal_size(fallback=(80, 24)).columns)
    dash = "-" if _ASCII_FALLBACK else "─"
    if label:
        side = (cols - len(label) - 2) // 2
        line = f"{dash * side} {label} {dash * (cols - side - len(label) - 2)}"
    else:
        line = dash * cols
    _emit(f"{Style.DIM}{line}{Style.RESET_ALL}", sink=output_sink)

def print_audit_summary(ok: int, warnings: int, unknowns: int,
                        output_sink: Callable[[str], None] | None = None):
    """Prints a compound-colored audit result line."""
    _emit(
        f"{Style.DIM}Audit complete:{Style.RESET_ALL}  "
        f"{Fore.GREEN}{ok} OK{Style.RESET_ALL}"
        f"{Style.DIM}  —  {Style.RESET_ALL}"
        f"{Fore.YELLOW}{warnings} need attention{Style.RESET_ALL}"
        f"{Style.DIM}  —  {unknowns} unknown{Style.RESET_ALL}",
        sink=output_sink,
    )

def print_finding(label: str, message: str, status: str,
                  output_sink: Callable[[str], None] | None = None):
    """Prints a finding with a status-colored bracket label and plain message."""
    status_color = {
        "OK":      Fore.GREEN,
        "WARNING": Fore.YELLOW,
        "ERROR":   Fore.RED,
    }.get(status, Fore.WHITE)
    _emit(f"  {status_color}[{label.upper()}]{Style.RESET_ALL} {message}", sink=output_sink)

def print_proposal(num: int, severity: str, title: str,
                   explanation: str, action: str, can_auto_fix: bool,
                   output_sink: Callable[[str], None] | None = None):
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
    _emit(f"\n{severity_color}{Style.BRIGHT}[{num}] {severity} — {title}{Style.RESET_ALL}",
          sink=output_sink)
    _emit(f"    {Fore.WHITE}{explanation}{Style.RESET_ALL}", sink=output_sink)
    _emit(f"    {Style.DIM}Fix: {action}  {fix_tag}{Style.RESET_ALL}", sink=output_sink)

def prompt_confirm(question: str) -> bool:
    """Branded yes/no prompt for non-system decisions (e.g. model download).

    Late-lookup: reads ``_CONFIRM_HANDLER`` at call time so a GUI bridge
    swap reaches every caller, including modules imported before the swap.
    """
    handler = _CONFIRM_HANDLER
    if handler is not None:
        return handler(question)
    print(f"{Fore.MAGENTA}{question} [y/n]: {Style.RESET_ALL}", end="", flush=True)
    return input().strip().lower() in ("y", "yes")

def prompt_approval(action_description: str) -> bool:
    """Prompts the user for yes/no approval for a specific action.

    Late-lookup: reads ``_APPROVAL_HANDLER`` at call time, so a GUI bridge
    swap reaches every caller — including pipeline modules already imported
    before the bridge installs its Qt-dialog handler.
    """
    handler = _APPROVAL_HANDLER
    if handler is not None:
        return handler(action_description)
    print(f"\n{Fore.MAGENTA}{Style.BRIGHT}? Requires Approval:{Style.RESET_ALL} {action_description}")
    while True:
        response = input("Proceed? [y/n]: ").strip().lower()
        if response in ['y', 'yes']:
            return True
        if response in ['n', 'no', '']:
            return False
        print(f"{Fore.RED}Invalid input. Please enter 'y' or 'n'.{Style.RESET_ALL}")


def prompt_pause(message: str = "") -> None:
    """Pause until the user acknowledges; auto-continues in GUI mode.

    Late-lookup: reads ``_PAUSE_HANDLER`` at call time so a GUI bridge swap
    reaches every caller. CLI fallback prints ``message`` (if any) via
    ``print_prompt`` and then blocks on ``input()``. The GUI bridge handler
    is a no-op so windowed mode never tries to read from a missing stdin.
    """
    handler = _PAUSE_HANDLER
    if handler is not None:
        handler(message)
        return
    if message:
        print_prompt(message)
    try:
        input()
    except (EOFError, RuntimeError, OSError):
        pass  # no stdin available — skip silently


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
