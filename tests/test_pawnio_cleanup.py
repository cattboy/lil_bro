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
             patch("src.pipeline.post_run_cleanup._find_pawnio_setup_exe", return_value=None), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_oem_inf", return_value=None), \
             patch("subprocess.run", return_value=sc_not_found) as mock_run:
            _uninstall_pawnio()
            # Only _pawnio_service_exists() should be called (returns not-found -> early exit)
            assert mock_run.call_count == 1

    def test_stops_service_before_uninstall(self):
        """sc stop must precede the pawnio_setup.exe -uninstall call."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 1  STOPPED")
        setup_ok  = self._make_sc_result(0)

        call_order: list[str] = []

        def side_effect(*args, **kwargs):
            cmd = args[0]
            tag = str(cmd[1]) if len(cmd) > 1 else str(cmd[0])
            call_order.append(tag)
            if "pawnio_setup" in str(cmd[0]):
                return setup_ok
            return sc_found

        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_setup_exe",
                   return_value="C:/fake/pawnio_setup.exe"), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_oem_inf", return_value=None), \
             patch("subprocess.run", side_effect=side_effect), \
             patch("time.sleep"):
            _uninstall_pawnio()

        assert "stop" in call_order, "sc stop was not called"
        assert "-uninstall" in call_order, "pawnio_setup.exe -uninstall was not called"
        assert call_order.index("stop") < call_order.index("-uninstall"), \
            "sc stop must precede -uninstall"


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


# ---------------------------------------------------------------------------
# _cleanup_cwd_tempdir
# ---------------------------------------------------------------------------

class TestCleanupCwdTempdir:

    def test_removes_lil_bro_dir_when_present(self, tmp_path, monkeypatch):
        from src.pipeline.post_run_cleanup import _cleanup_cwd_tempdir
        lil_bro_dir = tmp_path / "lil_bro"
        lil_bro_dir.mkdir()
        (lil_bro_dir / "artifact.tmp").touch()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup.action_logger"):
            _cleanup_cwd_tempdir()
        assert not lil_bro_dir.exists()

    def test_noop_when_dir_absent(self, tmp_path, monkeypatch):
        from src.pipeline.post_run_cleanup import _cleanup_cwd_tempdir
        monkeypatch.chdir(tmp_path)
        _cleanup_cwd_tempdir()  # must not raise


# ---------------------------------------------------------------------------
# _run_sc — return codes
# ---------------------------------------------------------------------------

class TestRunSc:

    def _call(self, returncode: int):
        from src.pipeline.post_run_cleanup import _run_sc
        mock_result = MagicMock()
        mock_result.returncode = returncode
        with patch("subprocess.run", return_value=mock_result):
            return _run_sc("stop", "PawnIO")

    def test_true_on_success(self):
        assert self._call(0) is True

    def test_true_on_service_not_exist(self):
        assert self._call(1060) is True

    def test_true_on_not_started(self):
        assert self._call(1062) is True

    def test_true_on_marked_for_deletion(self):
        assert self._call(1072) is True

    def test_false_on_unexpected_code(self):
        assert self._call(5) is False

    def test_false_when_subprocess_raises(self):
        from src.pipeline.post_run_cleanup import _run_sc
        with patch("subprocess.run", side_effect=Exception("timeout")):
            assert _run_sc("stop", "PawnIO") is False


# ---------------------------------------------------------------------------
# _find_pawnio_oem_inf
# ---------------------------------------------------------------------------

class TestFindPawnioOemInf:

    def _run_with_stdout(self, stdout: str, returncode: int = 0):
        from src.pipeline.post_run_cleanup import _find_pawnio_oem_inf
        mock_result = MagicMock()
        mock_result.returncode = returncode
        mock_result.stdout = stdout
        with patch("subprocess.run", return_value=mock_result):
            return _find_pawnio_oem_inf()

    def test_returns_oem_inf_when_pawnio_found(self):
        stdout = (
            "Published Name:  oem12.inf\n"
            "Original Name:   pawnio.inf\n"
            "Provider Name:   PawnIO\n"
            "\n"
            "Published Name:  oem5.inf\n"
            "Original Name:   other.inf\n"
            "Provider Name:   SomeOther\n"
        )
        assert self._run_with_stdout(stdout) == "oem12.inf"

    def test_returns_none_when_no_pawnio_entry(self):
        stdout = (
            "Published Name:  oem5.inf\n"
            "Original Name:   other.inf\n"
            "Provider Name:   SomeOther\n"
        )
        assert self._run_with_stdout(stdout) is None

    def test_returns_none_when_subprocess_fails(self):
        from src.pipeline.post_run_cleanup import _find_pawnio_oem_inf
        with patch("subprocess.run", side_effect=Exception("pnputil missing")):
            assert _find_pawnio_oem_inf() is None


# ---------------------------------------------------------------------------
# post_run_cleanup — orchestrator
# ---------------------------------------------------------------------------

class TestPostRunCleanup:

    def test_none_lhm_does_not_raise(self, tmp_path, monkeypatch):
        from src.pipeline.post_run_cleanup import post_run_cleanup
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup._uninstall_pawnio"), \
             patch("src.pipeline.post_run_cleanup._cleanup_cwd_tempdir"), \
             patch("src.pipeline.post_run_cleanup._cleanup_stale_mei"), \
             patch("src.pipeline.post_run_cleanup.print_info"), \
             patch("src.pipeline.post_run_cleanup.print_dim"):
            post_run_cleanup(lhm=None)  # must not raise

    def test_lhm_stop_called_when_provided(self, tmp_path, monkeypatch):
        from src.pipeline.post_run_cleanup import post_run_cleanup
        mock_lhm = MagicMock()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup._uninstall_pawnio"), \
             patch("src.pipeline.post_run_cleanup._cleanup_cwd_tempdir"), \
             patch("src.pipeline.post_run_cleanup._cleanup_stale_mei"), \
             patch("src.pipeline.post_run_cleanup.print_info"), \
             patch("src.pipeline.post_run_cleanup.print_dim"):
            post_run_cleanup(lhm=mock_lhm)
        mock_lhm.stop.assert_called_once()
