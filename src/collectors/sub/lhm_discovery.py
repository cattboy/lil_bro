"""LibreHardwareMonitor / lhm-server executable discovery.

Searches a fixed list of common locations for a thermal-sensor-server binary
and returns the first match. Pure file-existence check; no subprocess.

Note: Imports from this module are an implementation detail of
``lhm_sidecar``. External callers should import via the ``lhm_sidecar``
re-exports so that ``unittest.mock.patch("src.collectors.sub.lhm_sidecar.X")``
continues to work.
"""

import os
import sys
from typing import Optional

__all__ = ["find_lhm_executable", "_LHM_SEARCH_PATHS", "_PROJECT_ROOT"]


# Search order for thermal sensor server binaries.
# lhm-server.exe (custom minimal server) is checked first; falling back to
# a user-installed full LibreHardwareMonitor installation.
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

_LHM_SEARCH_PATHS = [
    # 1. PyInstaller frozen bundle -- sys._MEIPASS/tools/lhm-server.exe
    os.path.join(getattr(sys, "_MEIPASS", _PROJECT_ROOT), "tools", "lhm-server.exe"),
    # 2. Next to the running executable -- portable deployment (frozen .exe)
    os.path.join(os.path.dirname(sys.executable), "tools", "lhm-server.exe"),
    # 3. Source-tree dev path -- tools/lhm-server/dist/lhm-server.exe
    os.path.join(_PROJECT_ROOT, "tools", "lhm-server", "dist", "lhm-server.exe"),
    # 4. Full LibreHardwareMonitor installation (user-installed)
    os.path.join(_PROJECT_ROOT, "tools", "LibreHardwareMonitor", "LibreHardwareMonitor.exe"),
    r"C:\Program Files\LibreHardwareMonitor\LibreHardwareMonitor.exe",
    r"C:\Program Files (x86)\LibreHardwareMonitor\LibreHardwareMonitor.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\LibreHardwareMonitor\LibreHardwareMonitor.exe"),
]


def find_lhm_executable() -> tuple[Optional[str], bool]:
    """Search for a thermal sensor server binary.

    Returns:
        (path, is_custom_server) where:
        - path is the absolute path to the binary, or None if not found.
        - is_custom_server is True for lhm-server.exe (custom minimal server),
          False for the full LibreHardwareMonitor application.
    """
    for path in _LHM_SEARCH_PATHS:
        if os.path.isfile(path):
            is_custom = os.path.basename(path) == "lhm-server.exe"
            return path, is_custom
    return None, False
