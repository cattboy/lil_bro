"""Platform-level OS helpers — safe to import on any OS.

Centralizes the is_admin() check (previously duplicated in bootstrapper.py,
post_run_cleanup.py, and lhm_sidecar.py) and exposes IS_WINDOWS for tests
that need to skip Windows-only code paths.
"""

import ctypes  # safe on all OSes; windll is only accessed on Windows
import sys

IS_WINDOWS = sys.platform == "win32"


def is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    if not IS_WINDOWS:
        return False
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False
