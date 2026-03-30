"""
Centralized path helper — all runtime-writable paths under ./lil_bro/.

When running as a portable .exe, all temp files (logs, specs) are written
to a ``lil_bro/`` folder in the current working directory (next to the .exe).
This keeps the tool fully self-contained and leaves no trace in %APPDATA%.

The GGUF model (%APPDATA%\\lil_bro\\models\\) is handled separately by
model_loader.py — it lives in %APPDATA% because it is a persistent 4.5 GB
download that should survive between runs.
"""

from pathlib import Path


def get_appdata_dir() -> Path:
    """Return ``./lil_bro`` (CWD-relative), creating it if needed."""
    base = Path.cwd() / "lil_bro"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_logs_dir() -> Path:
    """Return ``./lil_bro/logs``, creating it if needed."""
    d = get_appdata_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_specs_path() -> Path:
    """Return the path for ``full_specs.json``."""
    return get_logs_dir() / "full_specs.json"


def get_action_log_path() -> Path:
    """Return the path for the persistent action log (CWD root, next to the .exe)."""
    return Path.cwd() / "lil_bro_actions.log"
