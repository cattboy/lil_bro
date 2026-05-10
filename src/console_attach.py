"""Win32 console attach for the single-exe ``--terminal`` flag.

The PyInstaller spec ships lil_bro as a windowed exe (``console=False``).
When the user runs ``lil_bro.exe --terminal`` from cmd.exe or Windows
Terminal, this module binds the (windowed) process's stdio to the parent
console so the existing CLI ``print()`` / ``input()`` calls work as
they always have.

Strategy (per design plan, locked in CEO + Eng review):

1. ``AttachConsole(ATTACH_PARENT_PROCESS)`` — bind to the caller's console.
2. If that fails (no parent console — shortcut / Explorer launch), fall
   back to ``AllocConsole()`` which pops a fresh console window.
3. Re-bind ``sys.stdin/stdout/stderr`` to ``CONIN$`` / ``CONOUT$`` so
   Python's standard streams flow into the now-attached console.

Known limitations (documented in README):

- PowerShell ISE / certain Windows Terminal tab configs may drop output.
- ``lil_bro.exe --terminal > output.txt`` (output redirection) breaks
  after the rebind, since stdio is forcibly attached to ``CONOUT$``.
  Workaround: pass ``--debug`` to write ``lil_bro_debug.log`` instead.
"""

from __future__ import annotations

import sys

ATTACH_PARENT_PROCESS = -1  # winbase.h: (DWORD)-1


def attach() -> None:
    """Bind the windowed process to a console (parent if any, else fresh).

    No-op on non-Windows. Also no-op when stdio is already wired to a real
    console (e.g., running ``python -m src.main`` in development against
    the source tree, or running an old ``console=True`` build).
    """
    if sys.platform != "win32":
        return
    if sys.stdout is not None and getattr(sys.stdout, "isatty", lambda: False)():
        return

    import ctypes

    kernel32 = ctypes.windll.kernel32
    if not kernel32.AttachConsole(ATTACH_PARENT_PROCESS):
        if not kernel32.AllocConsole():
            return  # Give up quietly — caller will see no output.

    _rebind_stdio()

    # Re-initialize colorama against the freshly-attached console stdout.
    # ``src.utils.formatting`` calls ``colorama.init(autoreset=True)`` at
    # import time, but in windowed PyInstaller mode that init runs against
    # the bootloader's null stdio sink — the one we just replaced via
    # _rebind_stdio() above. Without re-initialization, every print()
    # downstream of attach() emits raw ESC[..m sequences.
    try:
        from colorama import init
        init(autoreset=True)
    except Exception:
        pass


def _rebind_stdio() -> None:
    """Point sys.stdin/stdout/stderr at the freshly-attached console."""
    try:
        sys.stdin = open("CONIN$", "r", encoding="utf-8", errors="replace")
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace", buffering=1)
    except OSError:
        # Some PyInstaller builds open in odd states; better to lose
        # output than to crash the program before the user sees anything.
        pass
