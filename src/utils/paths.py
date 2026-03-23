"""
Centralized path helper — all runtime-writable paths under %APPDATA%\\lil_bro.

Mirrors the pattern used by model_loader.py for the GGUF model cache.
When running from a frozen PyInstaller .exe, the install directory is
read-only, so logs, specs, and other mutable data go to %APPDATA%.
"""

import os
from pathlib import Path


def get_appdata_dir() -> Path:
    """Return ``%APPDATA%\\lil_bro``, creating it if needed."""
    appdata = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    base = Path(appdata) / "lil_bro"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_logs_dir() -> Path:
    """Return ``%APPDATA%\\lil_bro\\logs``, creating it if needed."""
    d = get_appdata_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_specs_path() -> Path:
    """Return the path for ``full_specs.json``."""
    return get_logs_dir() / "full_specs.json"


def get_action_log_path() -> Path:
    """Return the path for the action log file."""
    return get_logs_dir() / "lil_bro_actions.log"
