r"""Unit tests for src/utils/pawnio_check.py — PawnIO install-state checks.

The reliable "usable" signal is the ``\\.\PawnIO`` device node (NOT a System32 /
Program Files ``PawnIOLib.dll`` path): a registered service whose device node is
gone (a half-uninstall leftover) must classify as "broken", not "installed". Every
check is best-effort and must never raise.
"""

import ctypes
from unittest.mock import MagicMock, patch

_INVALID = ctypes.c_void_p(-1).value


# ── is_pawnio_service_registered (registry key) ───────────────────────────────

class TestServiceRegistered:
    def test_true_when_service_key_exists(self):
        import winreg
        from src.utils.pawnio_check import is_pawnio_service_registered, _PAWNIO_SERVICE_KEY
        with patch("winreg.OpenKey") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            assert is_pawnio_service_registered() is True
            mock_open.assert_called_once_with(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_SERVICE_KEY)

    def test_false_when_missing(self):
        from src.utils.pawnio_check import is_pawnio_service_registered
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            assert is_pawnio_service_registered() is False

    def test_false_and_no_raise_on_oserror(self):
        from src.utils.pawnio_check import is_pawnio_service_registered
        with patch("winreg.OpenKey", side_effect=OSError("access denied")):
            assert is_pawnio_service_registered() is False

    def test_reads_services_not_uninstall(self):
        from src.utils.pawnio_check import _PAWNIO_SERVICE_KEY
        assert "Services" in _PAWNIO_SERVICE_KEY
        assert "Uninstall" not in _PAWNIO_SERVICE_KEY


# ── is_pawnio_device_present (\\.\PawnIO openability) ──────────────────────────

class TestDevicePresent:
    @staticmethod
    def _kernel32(handle):
        k = MagicMock()
        k.CreateFileW.return_value = handle
        return k

    def test_true_when_handle_valid(self):
        from src.utils.pawnio_check import is_pawnio_device_present
        k = self._kernel32(0x1234)
        with patch("src.utils.pawnio_check.ctypes.WinDLL", return_value=k):
            assert is_pawnio_device_present() is True
            k.CloseHandle.assert_called_once()

    def test_true_when_access_denied_means_exists(self):
        """Non-admin open of an EXISTING device returns ERROR_ACCESS_DENIED (5)."""
        from src.utils.pawnio_check import is_pawnio_device_present
        k = self._kernel32(_INVALID)
        with patch("src.utils.pawnio_check.ctypes.WinDLL", return_value=k), \
             patch("src.utils.pawnio_check.ctypes.get_last_error", return_value=5):
            assert is_pawnio_device_present() is True
            k.CloseHandle.assert_not_called()

    def test_false_when_file_not_found(self):
        from src.utils.pawnio_check import is_pawnio_device_present
        k = self._kernel32(_INVALID)
        with patch("src.utils.pawnio_check.ctypes.WinDLL", return_value=k), \
             patch("src.utils.pawnio_check.ctypes.get_last_error", return_value=2):
            assert is_pawnio_device_present() is False

    def test_false_and_no_raise_on_exception(self):
        from src.utils.pawnio_check import is_pawnio_device_present
        with patch("src.utils.pawnio_check.ctypes.WinDLL", side_effect=OSError("boom")):
            assert is_pawnio_device_present() is False


# ── pawnio_install_state / is_pawnio_usable (the tri-state) ──────────────────

class TestInstallState:
    @staticmethod
    def _patch(device, registered):
        return patch.multiple(
            "src.utils.pawnio_check",
            is_pawnio_device_present=MagicMock(return_value=device),
            is_pawnio_service_registered=MagicMock(return_value=registered),
        )

    def test_usable_when_device_present(self):
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(device=True, registered=True):
            assert pawnio_install_state() == "usable"
            assert is_pawnio_usable() is True

    def test_usable_ignores_service_key(self):
        """Device present is sufficient even if the service-key probe disagrees."""
        from src.utils.pawnio_check import pawnio_install_state
        with self._patch(device=True, registered=False):
            assert pawnio_install_state() == "usable"

    def test_broken_when_no_device_but_registered(self):
        """THE bug: service key lingers, device node gone -> broken, NOT usable."""
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(device=False, registered=True):
            assert pawnio_install_state() == "broken"
            assert is_pawnio_usable() is False

    def test_absent_when_no_device_no_service(self):
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(device=False, registered=False):
            assert pawnio_install_state() == "absent"
            assert is_pawnio_usable() is False
