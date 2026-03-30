"""
Post-run cleanup -- removes all runtime artifacts from the operating system.

Ensures lil_bro leaves no trace after exit:
  - Stops the LHM sidecar process
  - Stops and uninstalls the PawnIO kernel driver service
  - Removes PawnIO.sys from System32\\drivers
  - Cleans the PawnIO registry entry
  - Removes leftover tools from %APPDATA%\\lil_bro\\tools (backward compat)

The GGUF model (%APPDATA%\\lil_bro\\models\\) is preserved -- it was
downloaded with explicit user consent and is expensive to re-fetch.
"""

import ctypes
import os
import shutil
import subprocess
import time
import winreg
from pathlib import Path
from typing import Optional

from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.utils.formatting import print_info, print_warning, print_dim
from src.utils.action_logger import action_logger

_PAWNIO_SERVICE = "PawnIO"
_PAWNIO_REGISTRY_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO"


def _is_admin() -> bool:
    """Return True if the current process has administrator privileges."""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def _run_sc(*args: str) -> bool:
    """Run an sc.exe command. Returns True on success or if the service doesn't exist."""
    try:
        result = subprocess.run(
            ["sc", *args],
            capture_output=True, timeout=10, text=True,
        )
        # 0 = success, 1060 = service does not exist, 1062 = service not started
        return result.returncode in (0, 1060, 1062)
    except Exception:
        return False


def _uninstall_pawnio() -> None:
    """Stop and remove the PawnIO kernel driver, its System32 file, and registry key.

    Requires admin privileges -- skips silently if not elevated, since PawnIO
    would not have been installed without admin in the first place.
    """
    if not _is_admin():
        return

    # Check if PawnIO is even present before doing anything
    pawnio_exists = not _run_sc("query", _PAWNIO_SERVICE)  # query fails → service absent
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    driver_path = os.path.join(sys_root, "System32", "drivers", "PawnIO.sys")
    driver_on_disk = os.path.isfile(driver_path)

    if not pawnio_exists and not driver_on_disk:
        return  # nothing to clean

    # 1. Stop the running driver
    _run_sc("stop", _PAWNIO_SERVICE)
    time.sleep(0.5)  # brief settle time for driver unload

    # 2. Delete the service registration
    if _run_sc("delete", _PAWNIO_SERVICE):
        action_logger.log_action("Cleanup", "PawnIO service removed")

    # 3. Remove the .sys file from System32\drivers
    if driver_on_disk:
        try:
            os.remove(driver_path)
            action_logger.log_action("Cleanup", f"Removed {driver_path}")
        except OSError as e:
            print_warning(f"Could not remove {driver_path}: {e}")

    # 4. Remove the Uninstall registry key
    try:
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_REGISTRY_KEY)
    except FileNotFoundError:
        pass
    except OSError:
        pass


def _cleanup_appdata() -> None:
    """Remove leftover tools from %APPDATA%\\lil_bro\\tools (backward compat).

    Preserves logs/ (persistent across runs) and models/ (user-initiated download).
    """
    appdata_env = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    appdata = Path(appdata_env) / "lil_bro"
    if not appdata.is_dir():
        return

    target = appdata / "tools"
    if target.is_dir():
        try:
            shutil.rmtree(target)
        except OSError:
            pass

    # Remove the base dir if nothing remains (logs/ and models/ normally keep it populated)
    try:
        if not any(appdata.iterdir()):
            appdata.rmdir()
    except OSError:
        pass


def post_run_cleanup(lhm: Optional[LHMSidecar]) -> None:
    """Tear down all services and remove all runtime artifacts.

    Call this in the outermost finally block of main(). Accepts None
    for the sidecar handle (e.g. if startup failed before LHM launched).
    Swallows all exceptions -- cleanup must never mask the original error.
    """
    print_info("Cleaning up...")

    # 1. Kill the LHM sidecar process
    if lhm is not None:
        try:
            lhm.stop()
        except Exception:
            pass

    # 2. Uninstall PawnIO kernel driver + service + registry
    try:
        _uninstall_pawnio()
    except Exception:
        pass

    # 3. Remove runtime files from %APPDATA%
    try:
        _cleanup_appdata()
    except Exception:
        pass

    print_dim("  Cleanup complete.")
