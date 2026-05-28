"""Cinebench executable discovery.

Searches a fixed list of common install paths for a Cinebench binary.
Pure file-existence checks; no subprocess, no network.

Note: ``_CINEBENCH_SEARCH_PATHS`` is re-exported from ``cinebench`` for
backward compatibility, but the re-export is a read-only shim. Tests that
need to mutate the search list must target this module directly.
"""

import os
from pathlib import Path
from typing import Optional

_REPO_ROOT = str(Path(__file__).resolve().parent.parent.parent)

_CINEBENCH_SEARCH_PATHS = [
    # Placed next to lil_bro.exe by the user
    str(Path.cwd() / "Cinebench.exe"),
    # Bundled with lil_bro (future installer puts it here)
    os.path.join(_REPO_ROOT, "bench-exe", "Cinebench.exe"),
    # Maxon default installs
    r"C:\Program Files\Maxon Cinebench 2024\Cinebench.exe",
    r"C:\Program Files\Maxon Cinebench\Cinebench.exe",
    r"C:\Program Files\Maxon Cinema 4D 2026\Cinebench.exe",
    r"C:\Program Files\Maxon Cinema 4D 2024\Cinebench.exe",
    # Desktop shortcuts
    r"C:\Users\Public\Desktop\Cinebench.exe",
    os.path.expanduser(r"~\Desktop\Cinebench.exe"),
    # Steam
    os.path.expandvars(
        r"%ProgramFiles(x86)%\Steam\steamapps\common\Cinebench 2024\Cinebench.exe"
    ),
    os.path.expandvars(
        r"%ProgramFiles(x86)%\Steam\steamapps\common\Cinebench\Cinebench.exe"
    ),
    # User local apps
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cinebench 2024\Cinebench.exe"),
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Cinebench\Cinebench.exe"),
]


def find_cinebench() -> Optional[str]:
    """Return the first existing Cinebench path, or None if none found."""
    for path in _CINEBENCH_SEARCH_PATHS:
        if os.path.isfile(path):
            return path
    return None
