r"""Lightweight PawnIO install-state checks — read-only, no side effects.

A *usable* PawnIO is determined by the **device node** ``\\.\PawnIO`` — the ring-0
interface LibreHardwareMonitor and lil_bro's lhm-server open to read CPU sensors
(``PawnIOLib.cpp`` opens ``\Device\PawnIO``). The kernel driver creates that node
only when it is installed AND running AND bound to its PnP device, so the node's
presence — not a registered service key, and not any ``PawnIOLib.dll`` file — is the
reliable "is PawnIO usable" signal.

Why not check ``PawnIOLib.dll``: the official installer puts it in
``C:\Program Files\PawnIO`` (NOT System32), apps may bundle their own copy, and the
path is arch-/install-dir-dependent. The device node is location-independent and
tests the actual interface. ``pawnio_setup.exe`` installs the DLL and the device node
atomically, so a present device node implies a complete install.

Checking only the service registry key is a false-positive trap: an uninstall can
remove the device node + ``C:\Program Files\PawnIO`` while leaving the
``Services\PawnIO`` key behind (e.g. ``sc delete`` returning 1072 =
marked-for-deletion-until-reboot), which the old service-only check reported as
"installed" while LibreHardwareMonitor correctly reported "not installed".

All functions are best-effort and never raise — they run on diagnostic / startup
paths that must not crash the app.
"""

import ctypes

# PawnIO is a kernel driver service — its registry presence is under Services,
# not the Uninstall hive (which is only for MSI/NSIS installers).
_PAWNIO_SERVICE_KEY = r"SYSTEM\CurrentControlSet\Services\PawnIO"
# Win32 path to the PawnIO device object (\DosDevices\PawnIO -> \Device\PawnIO).
_PAWNIO_DEVICE_PATH = r"\\.\PawnIO"
# CreateFile / error constants.
_OPEN_EXISTING = 3
_FILE_SHARE_RW = 0x00000001 | 0x00000002  # FILE_SHARE_READ | FILE_SHARE_WRITE
_INVALID_HANDLE = ctypes.c_void_p(-1).value
_ERROR_ACCESS_DENIED = 5


def is_pawnio_service_registered() -> bool:
    """Return True if the PawnIO kernel driver service is registered with the SCM.

    Used only for the ownership snapshot and to distinguish "broken" from "absent" —
    it is NOT a usability signal (the key can outlive a removed device node).
    """
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_SERVICE_KEY):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def is_pawnio_device_present() -> bool:
    r"""Return True if the PawnIO ring-0 device ``\\.\PawnIO`` exists (never raises).

    Opens the device requesting no access. A valid handle (closed immediately) OR
    ``ERROR_ACCESS_DENIED`` both mean the device EXISTS — access-denied only fires
    when the object is present but the caller lacks rights (a non-elevated process).
    Only FILE_NOT_FOUND / PATH_NOT_FOUND (or any other failure) means "not present".
    This existence test is therefore admin-independent.
    """
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        create_file = kernel32.CreateFileW
        create_file.restype = ctypes.c_void_p
        create_file.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
        ]
        handle = create_file(
            _PAWNIO_DEVICE_PATH, 0, _FILE_SHARE_RW, None, _OPEN_EXISTING, 0, None
        )
    except Exception:
        return False
    if handle is not None and handle != _INVALID_HANDLE:
        try:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
        except Exception:
            pass  # safe: a handle leak on shutdown is harmless
        return True
    return ctypes.get_last_error() == _ERROR_ACCESS_DENIED


def pawnio_install_state() -> str:
    r"""Classify the PawnIO install into ``"usable"`` | ``"broken"`` | ``"absent"``.

    - ``"usable"``: the ``\\.\PawnIO`` device node is present (driver installed +
      running + bound — CPU sensors will read).
    - ``"broken"``: no device node, but the service key is still registered (the
      half-installed leftover — installed-but-won't-work).
    - ``"absent"``: no device node and no service key (nothing installed).
    """
    if is_pawnio_device_present():
        return "usable"
    return "broken" if is_pawnio_service_registered() else "absent"


def is_pawnio_usable() -> bool:
    """Return True only if PawnIO is fully usable (the ring-0 device node is present)."""
    return is_pawnio_device_present()
