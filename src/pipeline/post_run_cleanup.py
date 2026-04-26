"""
Post-run cleanup -- removes all runtime artifacts from the operating system.

Ensures lil_bro leaves no trace after exit:
  - Stops the LHM sidecar process
  - Stops and uninstalls the PawnIO kernel driver service
  - Removes PawnIO.sys from System32\\drivers
  - Removes the ./lil_bro/ temp folder created in the CWD during this run

The GGUF model (%APPDATA%\\lil_bro\\models\\) is preserved -- it was
downloaded with explicit user consent and is expensive to re-fetch.
"""

import ctypes
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from src.collectors.sub.lhm_sidecar import LHMSidecar
from src.utils.formatting import print_info, print_warning, print_dim
from src.utils.action_logger import action_logger
from src.utils.debug_logger import get_debug_logger
from src.utils.platform import is_admin

_PAWNIO_SERVICE = "PawnIO"
_PAWNIO_UNINSTALL_KEY = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO"
_MOVEFILE_DELAY_UNTIL_REBOOT = 4


def _pawnio_service_exists() -> bool:
    """Return True if the PawnIO service is registered with the SCM."""
    try:
        result = subprocess.run(
            ["sc", "query", _PAWNIO_SERVICE],
            capture_output=True, timeout=10, text=True,
        )
        # rc=0: service found; rc=1060: service does not exist
        return result.returncode == 0
    except Exception:
        return False


def _run_sc(*args: str) -> bool:
    """Run an sc.exe stop/delete command. Returns True on success or no-op."""
    try:
        result = subprocess.run(
            ["sc", *args],
            capture_output=True, timeout=10, text=True,
        )
        # 0 = success, 1060 = service does not exist, 1062 = service not started
        return result.returncode in (0, 1060, 1062)
    except Exception:
        return False


def _wait_for_driver_stopped(timeout: float = 10.0) -> bool:
    """Poll sc query until PawnIO reports STOPPED or disappears. Returns True when safe."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(
                ["sc", "query", _PAWNIO_SERVICE],
                capture_output=True, timeout=5, text=True,
            )
            if result.returncode == 1060:  # service no longer exists
                return True
            if "STOPPED" in result.stdout:
                return True
        except Exception:
            return True
        time.sleep(0.5)
    return False


def _find_pawnio_oem_inf() -> "str | None":
    """Return the OEM INF name (e.g. 'oem12.inf') for PawnIO in the Driver Store, or None."""
    try:
        result = subprocess.run(
            ["pnputil", "/enum-drivers"],
            capture_output=True, timeout=15, text=True,
        )
        if result.returncode != 0:
            return None
        current_oem: "str | None" = None
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.lower().startswith("published name:"):
                current_oem = line.split(":", 1)[1].strip()
            elif "pawnio" in line.lower() and current_oem:
                return current_oem
            elif not line:
                current_oem = None
        return None
    except Exception:
        return None


def _run_pnputil(*args: str) -> bool:
    try:
        result = subprocess.run(
            ["pnputil", *args],
            capture_output=True, timeout=30, text=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _uninstall_pawnio(was_preinstalled: bool = False) -> None:
    """Stop and remove the PawnIO kernel driver and its System32 file.

    Requires admin privileges -- skips silently if not elevated, since PawnIO
    would not have been installed without admin in the first place.

    If was_preinstalled is True the driver was present before lil_bro launched
    (i.e. the user installed it via pawnio_setup.exe) and must not be touched.
    """
    if not is_admin():
        return
    if was_preinstalled:
        return

    pawnio_exists = _pawnio_service_exists()
    sys_root = os.environ.get("SystemRoot", r"C:\Windows")
    driver_path = os.path.join(sys_root, "System32", "drivers", "PawnIO.sys")
    driver_on_disk = os.path.isfile(driver_path)
    oem_inf = _find_pawnio_oem_inf()

    if not pawnio_exists and not driver_on_disk and not oem_inf:
        return  # nothing to clean

    # 1. Stop the running driver, then poll until kernel releases the lock
    if pawnio_exists:
        _run_sc("stop", _PAWNIO_SERVICE)
        _wait_for_driver_stopped()

    # 2. Driver Store path (pawnio_setup.exe install): pnputil removes the
    #    device node, service registration, and Driver Store entry in one shot.
    if oem_inf:
        if _run_pnputil("/delete-driver", oem_inf, "/uninstall"):
            action_logger.log_action("Cleanup", f"PawnIO removed from Driver Store ({oem_inf})")
        else:
            action_logger.log_action("Cleanup", f"pnputil /delete-driver {oem_inf} failed — falling back to sc delete")

    # 3. Legacy sc create fallback — handles installs that bypassed Driver Store.
    #    Re-check service existence: pnputil may have removed it already.
    if _pawnio_service_exists():
        if _run_sc("delete", _PAWNIO_SERVICE):
            action_logger.log_action("Cleanup", "PawnIO service removed (legacy)")

    # 4. Remove the .sys file from System32\drivers (legacy sc create path only;
    #    Driver Store installs keep the file in the Driver Store, not here).
    #    If the kernel still holds the file lock, schedule deletion on next reboot.
    if driver_on_disk:
        try:
            os.remove(driver_path)
            action_logger.log_action("Cleanup", f"Removed {driver_path}")
        except PermissionError:
            scheduled = ctypes.windll.kernel32.MoveFileExW(
                driver_path, None, _MOVEFILE_DELAY_UNTIL_REBOOT
            )
            if scheduled:
                action_logger.log_action(
                    "Cleanup", f"Scheduled {driver_path} for deletion on next reboot"
                )
                print_warning("PawnIO.sys is still locked by the kernel — will be removed on next reboot.")
            else:
                print_warning(f"Could not remove {driver_path}: driver locked by kernel")
        except OSError as e:
            print_warning(f"Could not remove {driver_path}: {e}")

    # 5. Remove the Uninstall sentinel key written by old lhm-server sc create installs
    try:
        import winreg
        winreg.DeleteKey(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_UNINSTALL_KEY)
    except (FileNotFoundError, OSError):
        pass


def _cleanup_cwd_tempdir() -> None:
    """Remove the ./lil_bro/ temp folder created in the CWD during this run."""
    lil_bro_dir = Path.cwd() / "lil_bro"
    if not lil_bro_dir.is_dir():
        return
    try:
        shutil.rmtree(lil_bro_dir)
        action_logger.log_action("Cleanup", "Removed runtime temp dir", str(lil_bro_dir))
    except OSError:
        pass


def _cleanup_stale_mei() -> None:
    """Remove orphaned _MEI* directories left by prior crashed runs.

    PyInstaller onefile extracts to CWD/_MEIxxxxxx (via runtime_tmpdir='.').
    Normal exits clean up automatically, but crashes leave orphans.
    Skip the current process's own _MEI directory (sys._MEIPASS).
    """
    import sys as _sys

    current_mei = getattr(_sys, "_MEIPASS", None)
    cwd = Path.cwd()

    for entry in cwd.iterdir():
        if not entry.is_dir() or not entry.name.startswith("_MEI"):
            continue
        # Don't delete our own extraction directory
        if current_mei and entry == Path(current_mei):
            continue
        try:
            shutil.rmtree(entry)
            action_logger.log_action("Cleanup", "Removed stale PyInstaller dir", str(entry))
        except OSError:
            pass


def post_run_cleanup(lhm: Optional[LHMSidecar], pawnio_was_preinstalled: bool = False) -> None:
    """Tear down all services and remove all runtime artifacts.

    Call this in the outermost finally block of main(). Accepts None
    for the sidecar handle (e.g. if startup failed before LHM launched).
    Swallows all exceptions -- cleanup must never mask the original error.
    """
    print_info("Cleaning up... lil_bro always leaves your system clean and tidy, like a true bro should.")

    # 1. Kill the LHM sidecar process
    if lhm is not None:
        try:
            lhm.stop()
        except Exception:
            get_debug_logger().warning("LHM sidecar stop failed during cleanup", exc_info=True)

    # 2. Uninstall PawnIO kernel driver + service + registry
    try:
        _uninstall_pawnio(was_preinstalled=pawnio_was_preinstalled)
    except Exception:
        get_debug_logger().warning("PawnIO uninstall failed during cleanup", exc_info=True)

    # 3. Remove CWD ./lil_bro/ temp folder
    try:
        _cleanup_cwd_tempdir()
    except Exception:
        get_debug_logger().warning("Temp dir cleanup failed during cleanup", exc_info=True)

    # 4. Remove orphaned _MEI* dirs from prior crashed runs
    try:
        _cleanup_stale_mei()
    except Exception:
        get_debug_logger().warning("Stale _MEI cleanup failed during cleanup", exc_info=True)

    print_dim("  Cleanup complete. lil_bro leaves no trace, just like a true bro should.")
