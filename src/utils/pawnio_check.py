"""Lightweight PawnIO install-state checks — read-only, no side effects.

A *usable* PawnIO requires TWO things, not just a registered service:
  1. the kernel driver service is registered AND RUNNING — the running driver
     creates the ``\\Device\\PawnIO`` node that ``PawnIOLib.dll`` opens; a
     registered-but-stopped service has no device node yet, and
  2. the user-mode ``PawnIOLib.dll`` is present in ``System32`` —
     LibreHardwareMonitorLib (and lil_bro's lhm-server sidecar) load it to open
     the ring-0 interface.

Checking only the service registry key is a false-positive trap: an uninstall
that removes ``PawnIOLib.dll`` but leaves the service behind (e.g. ``sc delete``
returning 1072 = marked-for-deletion-until-reboot) yields a registered+running
driver with no usable library. The old service-only check reported that as
"installed" while LibreHardwareMonitor itself correctly reported "not installed".

All functions are best-effort and never raise — they run on diagnostic / startup
paths that must not crash the app.
"""

import os
import subprocess

# PawnIO is a kernel driver service — its registry presence is under Services,
# not the Uninstall hive (which is only for MSI/NSIS installers).
_PAWNIO_SERVICE_KEY = r"SYSTEM\CurrentControlSet\Services\PawnIO"
_PAWNIO_SERVICE = "PawnIO"
# Hidden-window flag so the sc.exe probe never flashes a console window.
_CREATE_NO_WINDOW = 0x08000000


def is_pawnio_service_registered() -> bool:
    """Return True if the PawnIO kernel driver service is registered with the SCM."""
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_SERVICE_KEY):
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def is_pawnio_running() -> bool:
    """Return True if the PawnIO service is currently RUNNING (best-effort, never raises).

    Mirrors lhm-server's ``QueryPawnIoService``: parse ``sc query PawnIO`` stdout for
    the RUNNING state. The running driver is what creates the ``\\Device\\PawnIO``
    node that ``PawnIOLib.dll`` opens, so a registered-but-stopped service is not
    yet usable.
    """
    try:
        result = subprocess.run(
            ["sc", "query", _PAWNIO_SERVICE],
            capture_output=True, timeout=10, text=True,
            creationflags=_CREATE_NO_WINDOW,
        )
    except Exception:
        return False
    if result.returncode != 0:
        return False
    return "RUNNING" in (result.stdout or "")


def is_pawnio_lib_present() -> bool:
    """Return True if the user-mode ``PawnIOLib.dll`` is installed in ``System32``.

    This is the signal LibreHardwareMonitor itself uses; it is removed on uninstall
    while the service key can linger, so it is the reliable "is PawnIO usable" check.
    Never raises — a missing ``%SystemRoot%`` falls back to ``C:\\Windows``.
    """
    system_root = os.environ.get("SystemRoot", r"C:\Windows")
    return os.path.isfile(os.path.join(system_root, "System32", "PawnIOLib.dll"))


def pawnio_install_state() -> str:
    """Classify the PawnIO install into ``"usable"`` | ``"broken"`` | ``"absent"``.

    - ``"absent"``: service not registered and no library (nothing installed).
    - ``"usable"``: service registered AND running AND ``PawnIOLib.dll`` present.
    - ``"broken"``: installed but it won't read sensors — registered yet not
      running or missing the library (the half-installed state), OR the rare
      ``PawnIOLib.dll``-without-service artifact of a partial manual uninstall.
    """
    registered = is_pawnio_service_registered()
    lib = is_pawnio_lib_present()
    if not registered:
        return "broken" if lib else "absent"
    if is_pawnio_running() and lib:
        return "usable"
    return "broken"


def is_pawnio_usable() -> bool:
    """Return True only if PawnIO is fully usable (service running AND library present)."""
    return pawnio_install_state() == "usable"
