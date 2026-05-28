"""Windows console window manipulation — isolated ctypes IO.

Holds ``resize_console_window``. Re-exported via ``formatting`` so callers
continue to ``from src.utils.formatting import resize_console_window``.

Note: function-local ``import ctypes`` / ``import os`` are load-bearing for
existing test patches that target ``ctypes.windll`` directly. Do not hoist
these imports to module top — a future cleanup that switches to
``from ctypes import windll`` would break the patch silently.
"""


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
        pass  # safe: ctypes user32 call may fail on non-Windows or restricted contexts
