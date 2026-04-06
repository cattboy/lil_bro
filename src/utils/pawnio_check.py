"""Lightweight PawnIO installation check — read-only, no side effects."""

import winreg

# PawnIO is a kernel driver service — its registry presence is under Services,
# not the Uninstall hive (which is only for MSI/NSIS installers).
_PAWNIO_SERVICE_KEY = r"SYSTEM\CurrentControlSet\Services\PawnIO"


def is_pawnio_installed() -> bool:
    """Return True if the PawnIO kernel driver service is registered."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_SERVICE_KEY):
            return True
    except FileNotFoundError:
        return False
