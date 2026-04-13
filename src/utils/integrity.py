"""
SHA-256 file integrity verification for frozen builds.

Reads ``integrity.json`` from next to the .exe and verifies the exe hash.
Only runs when frozen (PyInstaller ``onefile`` mode).  Silently returns
True in dev mode or when no manifest is present.
"""

import hashlib
import json
import sys
from pathlib import Path

from src.utils.formatting import print_error, print_info, print_warning


def _get_exe_dir() -> Path:
    """Return the directory containing the .exe (frozen) or project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent.parent


def verify_integrity(silent_pass: bool = True) -> bool:
    """
    Verify the executable hash against the build manifest.

    Returns True if verification passes or is skipped.
    Prints warnings for mismatches but never blocks execution.
    """
    if not getattr(sys, "frozen", False):
        return True  # Dev mode — skip

    exe_dir = _get_exe_dir()
    manifest_path = exe_dir / "integrity.json"

    if not manifest_path.exists():
        print_error("integrity.json not found — cannot verify lil_bro.exe is safe.")
        print()
        print_info(
            "integrity.json is a security manifest that confirms your copy of\n"
            "  lil_bro.exe has not been tampered with or corrupted."
        )
        print()
        print_warning("To fix this:")
        print_warning("  1. Make sure integrity.json is in the same folder as lil_bro.exe.")
        print_warning("  2. If it is missing, re-extract the original .rar/.zip file.")
        print_warning(
            "  3. If this copy was given to you by someone you don't trust, or\n"
            "     downloaded from a random website — DO NOT USE IT.\n"
            "     Download a fresh copy from the official release page:\n"
            "     https://github.com/cattboy/lil_bro/releases"
        )
        input("\nPress ENTER to exit...")
        sys.exit(1)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return True  # Corrupted manifest — skip rather than block

    expected_hash = manifest.get("exe_hash")
    if not expected_hash:
        return True

    # Hash the .exe itself
    exe_path = Path(sys.executable)
    try:
        actual = hashlib.sha256(exe_path.read_bytes()).hexdigest()
    except Exception:
        return True  # Can't read own exe — skip

    if actual != expected_hash:
        print_warning(
            "Integrity check failed — lil_bro.exe may have been modified or corrupted.\n"
            "DO NOT USE THIS LIL_BRO.exe\n"
            "Only use lil_bro.exe from github releases page\n"
            "https://github.com/cattboy/lil_bro/releases" \
            "\n"
        )
        print_warning(
            f"  Expected: {expected_hash[:16]}...  Got: {actual[:16]}..."
        )
        return False

    return True
