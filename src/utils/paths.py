"""
Centralized path helper — all runtime-writable paths under ./lil_bro/.

When running as a portable .exe, all temp files and data snapshots are written
to a ``lil_bro/`` folder in the current working directory (next to the .exe).
This keeps the tool fully self-contained and leaves no trace in %APPDATA%.

Persistent files (action log, debug log) live at CWD root so they survive
the ``./lil_bro/`` cleanup that runs on exit.

The GGUF model (%APPDATA%\\lil_bro\\models\\) is handled separately by
model_loader.py — it lives in %APPDATA% because it is a persistent 4.5 GB
download that should survive between runs.
"""

from pathlib import Path


def get_lil_bro_dir() -> Path:
    """Return ``./lil_bro`` (CWD-relative), creating it if needed."""
    base = Path.cwd() / "lil_bro"
    base.mkdir(parents=True, exist_ok=True)
    return base


def get_logs_dir() -> Path:
    """Return ``./lil_bro/logs``, creating it if needed."""
    d = get_lil_bro_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_specs_path() -> Path:
    """Return the path for ``full_specs.json`` (data snapshot, not a log)."""
    return get_lil_bro_dir() / "full_specs.json"


def get_action_log_path() -> Path:
    """Return the path for the persistent action log (CWD root, survives cleanup)."""
    return Path.cwd() / "lil_bro_actions.log"


def get_debug_log_path() -> Path:
    """Return the path for the persistent debug log (CWD root, survives cleanup)."""
    return Path.cwd() / "lil_bro_debug.log"


def get_temp_dir() -> Path:
    """Return ``./lil_bro/tmp/``, creating it if needed.

    All subprocess temp files must use this instead of ``tempfile.gettempdir()``
    to avoid scattering artifacts in ``%TEMP%``.
    """
    d = get_lil_bro_dir() / "tmp"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_backups_dir() -> Path:
    """Return ``./lil_bro_backups/``, creating it if needed.

    CWD-root directory — survives ``post_run_cleanup.py`` deletion of ``./lil_bro/``.
    Used for NVIDIA .nip backups and the session manifest.
    """
    d = Path.cwd() / "lil_bro_backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_session_backup_path() -> Path:
    """Return the path to the session manifest: ``./lil_bro_backups/session_latest.json``."""
    return get_backups_dir() / "session_latest.json"
