"""Lightweight PawnIO installation check — read-only, no side effects."""

import winreg

_PAWNIO_UNINSTALL_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\PawnIO"
)


def is_pawnio_installed() -> bool:
    """Return True if PawnIO driver is registered in the Windows Uninstall registry."""
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_UNINSTALL_KEY):
            return True
    except FileNotFoundError:
        return False
