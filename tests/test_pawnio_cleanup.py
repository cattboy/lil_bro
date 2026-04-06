"""Regression tests for pawnio_check.py and post_run_cleanup._uninstall_pawnio."""

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# pawnio_check — correct registry key
# ---------------------------------------------------------------------------

class TestIsPawnioInstalled:
    """is_pawnio_installed() must read from the Services key, not Uninstall."""

    def test_returns_true_when_service_key_exists(self):
        import winreg
        from src.utils.pawnio_check import is_pawnio_installed, _PAWNIO_SERVICE_KEY
        with patch("winreg.OpenKey") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            assert is_pawnio_installed() is True
            mock_open.assert_called_once_with(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_SERVICE_KEY)

    def test_returns_false_when_service_key_missing(self):
        from src.utils.pawnio_check import is_pawnio_installed
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            assert is_pawnio_installed() is False

    def test_checks_services_not_uninstall(self):
        """Key must be under SYSTEM\\CurrentControlSet\\Services, never Uninstall."""
        from src.utils.pawnio_check import _PAWNIO_SERVICE_KEY
        assert "Services" in _PAWNIO_SERVICE_KEY
        assert "Uninstall" not in _PAWNIO_SERVICE_KEY


# ---------------------------------------------------------------------------
# _pawnio_service_exists — only True for rc=0
# ---------------------------------------------------------------------------

class TestPawnioServiceExists:
    """_pawnio_service_exists must return False when sc.exe returns 1060."""

    def _run(self, returncode: int):
        from src.pipeline.post_run_cleanup import _pawnio_service_exists
        mock_result = MagicMock()
        mock_result.returncode = returncode
        with patch("subprocess.run", return_value=mock_result):
            return _pawnio_service_exists()

    def test_true_when_service_found(self):
        assert self._run(0) is True

    def test_false_when_service_not_found(self):
        # rc=1060 is ERROR_SERVICE_DOES_NOT_EXIST — must be False, not True
        assert self._run(1060) is False

    def test_false_when_subprocess_raises(self):
        from src.pipeline.post_run_cleanup import _pawnio_service_exists
        with patch("subprocess.run", side_effect=Exception("timeout")):
            assert _pawnio_service_exists() is False


# ---------------------------------------------------------------------------
# _wait_for_driver_stopped
# ---------------------------------------------------------------------------

class TestWaitForDriverStopped:

    def test_returns_true_when_service_gone(self):
        from src.pipeline.post_run_cleanup import _wait_for_driver_stopped
        mock_result = MagicMock()
        mock_result.returncode = 1060  # service does not exist
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.sleep"):
            assert _wait_for_driver_stopped() is True

    def test_returns_true_when_stopped_in_output(self):
        from src.pipeline.post_run_cleanup import _wait_for_driver_stopped
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "STATE              : 1  STOPPED"
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.sleep"):
            assert _wait_for_driver_stopped() is True

    def test_returns_false_on_timeout(self):
        from src.pipeline.post_run_cleanup import _wait_for_driver_stopped
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "STATE              : 4  RUNNING"
        # Use a very short timeout so the test doesn't actually sleep
        with patch("subprocess.run", return_value=mock_result), \
             patch("time.sleep"), \
             patch("time.monotonic", side_effect=[0.0, 999.0]):
            assert _wait_for_driver_stopped(timeout=1.0) is False


# ---------------------------------------------------------------------------
# _uninstall_pawnio — integration of all three fixes
# ---------------------------------------------------------------------------

class TestUninstallPawnio:

    def _make_sc_result(self, returncode, stdout=""):
        r = MagicMock()
        r.returncode = returncode
        r.stdout = stdout
        return r

    def test_skips_when_not_admin(self):
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=False), \
             patch("subprocess.run") as mock_run:
            _uninstall_pawnio()
            mock_run.assert_not_called()

    def test_skips_when_nothing_to_clean(self):
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_not_found = self._make_sc_result(1060)
        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("subprocess.run", return_value=sc_not_found), \
             patch("os.path.isfile", return_value=False), \
             patch("os.remove") as mock_remove:
            _uninstall_pawnio()
            mock_remove.assert_not_called()

    def test_stops_service_before_deleting_file(self):
        """sc stop must precede the file removal attempt."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 1  STOPPED")
        sc_deleted = self._make_sc_result(0)
        sc_calls = iter([sc_found, sc_found, sc_deleted])

        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("subprocess.run", side_effect=lambda *a, **kw: next(sc_calls)), \
             patch("os.path.isfile", return_value=True), \
             patch("os.remove") as mock_remove, \
             patch("time.monotonic", side_effect=[0.0, 0.1, 999.0]), \
             patch("time.sleep"):
            _uninstall_pawnio()
            mock_remove.assert_called_once()

    def test_schedules_reboot_deletion_when_file_locked(self):
        """If os.remove raises PermissionError, MoveFileExW must be called."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 1  STOPPED")
        sc_deleted = self._make_sc_result(0)
        sc_calls = iter([sc_found, sc_found, sc_deleted])

        mock_kernel32 = MagicMock()
        mock_kernel32.MoveFileExW.return_value = 1  # success

        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("subprocess.run", side_effect=lambda *a, **kw: next(sc_calls)), \
             patch("os.path.isfile", return_value=True), \
             patch("os.remove", side_effect=PermissionError("locked")), \
             patch("ctypes.windll") as mock_windll, \
             patch("time.monotonic", side_effect=[0.0, 0.1, 999.0]), \
             patch("time.sleep"), \
             patch("src.pipeline.post_run_cleanup.print_warning"):
            mock_windll.kernel32 = mock_kernel32
            mock_windll.shell32.IsUserAnAdmin.return_value = 1
            _uninstall_pawnio()
            mock_kernel32.MoveFileExW.assert_called_once()
            # Second arg must be None (delete on reboot), third must be 4
            args = mock_kernel32.MoveFileExW.call_args[0]
            assert args[1] is None
            assert args[2] == 4


# ---------------------------------------------------------------------------
# _cleanup_stale_mei — orphaned PyInstaller extraction dirs
# ---------------------------------------------------------------------------

class TestCleanupStaleMei:

    def test_no_mei_dirs_is_noop(self, tmp_path, monkeypatch):
        """When CWD has no _MEI dirs, nothing happens."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        (tmp_path / "somefile.txt").touch()
        monkeypatch.chdir(tmp_path)
        _cleanup_stale_mei()  # must not crash

    def test_removes_orphaned_mei_dir(self, tmp_path, monkeypatch):
        """Orphaned _MEI dirs (not our own) must be removed."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        orphan = tmp_path / "_MEI123456"
        orphan.mkdir()
        (orphan / "dummy.dll").touch()
        monkeypatch.chdir(tmp_path)
        assert orphan.exists()
        _cleanup_stale_mei()
        assert not orphan.exists()

    def test_skips_current_process_meipass(self, tmp_path, monkeypatch):
        """Must NOT delete our own _MEIPASS directory."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        our_mei = tmp_path / "_MEI999999"
        our_mei.mkdir()
        other_mei = tmp_path / "_MEI111111"
        other_mei.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys._MEIPASS", str(our_mei), raising=False)
        _cleanup_stale_mei()
        assert our_mei.exists(), "Must not delete current process _MEIPASS"
        assert not other_mei.exists(), "Must delete orphaned _MEI dirs"
