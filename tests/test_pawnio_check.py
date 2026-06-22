"""Unit tests for src/utils/pawnio_check.py — PawnIO install-state checks.

Covers the false-positive bug that caused the "no temps" report: a registered +
RUNNING PawnIO service with PawnIOLib.dll MISSING must classify as "broken"
(not usable), not "installed". Every check is best-effort and must never raise.
"""

from unittest.mock import MagicMock, patch


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


# ── is_pawnio_running (sc query → RUNNING) ────────────────────────────────────

class TestServiceRunning:
    @staticmethod
    def _result(returncode=0, stdout=""):
        r = MagicMock()
        r.returncode = returncode
        r.stdout = stdout
        return r

    def test_true_when_running(self):
        from src.utils.pawnio_check import is_pawnio_running
        out = "SERVICE_NAME: PawnIO\n        STATE   : 4  RUNNING"
        with patch("src.utils.pawnio_check.subprocess.run", return_value=self._result(0, out)):
            assert is_pawnio_running() is True

    def test_false_when_stopped(self):
        from src.utils.pawnio_check import is_pawnio_running
        out = "SERVICE_NAME: PawnIO\n        STATE   : 1  STOPPED"
        with patch("src.utils.pawnio_check.subprocess.run", return_value=self._result(0, out)):
            assert is_pawnio_running() is False

    def test_false_when_service_absent_rc1060(self):
        from src.utils.pawnio_check import is_pawnio_running
        with patch("src.utils.pawnio_check.subprocess.run", return_value=self._result(1060, "")):
            assert is_pawnio_running() is False

    def test_false_and_no_raise_on_exception(self):
        from src.utils.pawnio_check import is_pawnio_running
        with patch("src.utils.pawnio_check.subprocess.run", side_effect=OSError("boom")):
            assert is_pawnio_running() is False


# ── is_pawnio_lib_present (System32\PawnIOLib.dll) ────────────────────────────

class TestLibPresent:
    def test_true_when_dll_exists(self):
        from src.utils.pawnio_check import is_pawnio_lib_present
        with patch("os.path.isfile", return_value=True) as mock_isfile:
            assert is_pawnio_lib_present() is True
            called = mock_isfile.call_args[0][0]
            assert called.lower().endswith("system32\\pawniolib.dll")

    def test_false_when_dll_missing(self):
        from src.utils.pawnio_check import is_pawnio_lib_present
        with patch("os.path.isfile", return_value=False):
            assert is_pawnio_lib_present() is False

    def test_no_raise_when_systemroot_unset(self):
        from src.utils.pawnio_check import is_pawnio_lib_present
        with patch.dict("os.environ", {}, clear=True), \
             patch("os.path.isfile", return_value=False) as mock_isfile:
            assert is_pawnio_lib_present() is False
            called = mock_isfile.call_args[0][0]
            assert called.lower().startswith("c:\\windows")


# ── pawnio_install_state / is_pawnio_usable (the tri-state) ──────────────────

class TestInstallState:
    @staticmethod
    def _patch(registered, running, lib):
        return patch.multiple(
            "src.utils.pawnio_check",
            is_pawnio_service_registered=MagicMock(return_value=registered),
            is_pawnio_running=MagicMock(return_value=running),
            is_pawnio_lib_present=MagicMock(return_value=lib),
        )

    def test_usable_when_registered_running_lib(self):
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(True, True, True):
            assert pawnio_install_state() == "usable"
            assert is_pawnio_usable() is True

    def test_broken_when_running_but_no_lib(self):
        """THE bug: service running, PawnIOLib.dll missing -> broken, NOT usable."""
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(True, True, False):
            assert pawnio_install_state() == "broken"
            assert is_pawnio_usable() is False

    def test_broken_when_registered_not_running(self):
        """BLOCKER-1 edge: registered + lib present but service stopped -> broken
        (no \\Device\\PawnIO node until the driver actually runs)."""
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(True, False, True):
            assert pawnio_install_state() == "broken"
            assert is_pawnio_usable() is False

    def test_broken_when_lib_without_service(self):
        from src.utils.pawnio_check import pawnio_install_state
        with self._patch(False, False, True):
            assert pawnio_install_state() == "broken"

    def test_absent_when_nothing_installed(self):
        from src.utils.pawnio_check import pawnio_install_state, is_pawnio_usable
        with self._patch(False, False, False):
            assert pawnio_install_state() == "absent"
            assert is_pawnio_usable() is False
