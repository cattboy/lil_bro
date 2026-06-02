"""Surface the main window to the foreground after the splash closes.

Isolated ctypes IO, mirroring ``src.utils._console``. The Windows
foreground-lock makes a bare ``QWidget.show()`` flash the taskbar instead of
coming to the front when the app lost foreground during the (multi-second)
splash. This helper:

  1. Qt layer  — clear a restored-minimized state, raise Z-order, activate.
  2. Win32     — AttachThreadInput to the current foreground thread so
                 SetForegroundWindow is *permitted* (defeats the lock), detach.
  3. Fallback  — if foreground is still denied, FlashWindowEx the taskbar
                 button until the window is foregrounded.

Note: function-local ``import ctypes`` is load-bearing for tests that patch
``ctypes.windll`` directly (tests/test_foreground.py). Do not hoist it to module
top. The whole Win32 block is wrapped in ``try/except`` so it is a silent no-op
off-Windows or in restricted contexts.
"""

from __future__ import annotations

from PySide6.QtCore import Qt


def bring_to_foreground(window) -> None:
    """Reliably surface ``window`` to the foreground; silent no-op off-Windows."""
    # ── Qt layer (cross-platform) ──────────────────────────────────────
    try:
        state = window.windowState() & ~Qt.WindowState.WindowMinimized
        window.setWindowState(state | Qt.WindowState.WindowActive)
        window.raise_()
        window.activateWindow()
    except Exception:
        pass

    # ── Win32 foreground-lock bypass ───────────────────────────────────
    try:
        import ctypes

        user32   = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = int(window.winId())
        if not hwnd:
            return

        # De-iconify at the OS level if the prior session left it minimized.
        if user32.IsIconic(hwnd):
            user32.ShowWindow(hwnd, 9)   # SW_RESTORE

        # Attaching our input thread to the current foreground thread is what
        # makes SetForegroundWindow succeed; otherwise the OS only flashes the
        # taskbar button when the app is not already the foreground process.
        fg_hwnd  = user32.GetForegroundWindow()
        this_tid = kernel32.GetCurrentThreadId()
        fg_tid   = user32.GetWindowThreadProcessId(fg_hwnd, None)

        attached = False
        if fg_tid and fg_tid != this_tid:
            attached = bool(user32.AttachThreadInput(this_tid, fg_tid, True))
        try:
            user32.BringWindowToTop(hwnd)
            user32.SetForegroundWindow(hwnd)
        finally:
            if attached:
                user32.AttachThreadInput(this_tid, fg_tid, False)

        # Fallback: OS still denied foreground → flash the taskbar button.
        if user32.GetForegroundWindow() != hwnd:
            _flash_taskbar(user32, hwnd)
    except Exception:
        pass  # safe: ctypes/user32 unavailable off-Windows or restricted context


def _flash_taskbar(user32, hwnd: int) -> None:
    """Flash the taskbar button until the window comes to the foreground."""
    import ctypes

    class FLASHWINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_uint),
            ("hwnd", ctypes.c_void_p),
            ("dwFlags", ctypes.c_uint),
            ("uCount", ctypes.c_uint),
            ("dwTimeout", ctypes.c_uint),
        ]

    FLASHW_ALL       = 0x00000003
    FLASHW_TIMERNOFG = 0x0000000C   # flash until the window is foregrounded
    info = FLASHWINFO(
        ctypes.sizeof(FLASHWINFO), ctypes.c_void_p(hwnd),
        FLASHW_ALL | FLASHW_TIMERNOFG, 0, 0,
    )
    user32.FlashWindowEx(ctypes.byref(info))
