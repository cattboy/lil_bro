"""Regression tests for pawnio_check.py and post_run_cleanup._uninstall_pawnio."""

import subprocess
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# pawnio_check — correct registry key
# ---------------------------------------------------------------------------

class TestIsPawnioServiceRegistered:
    """is_pawnio_service_registered() must read from the Services key, not Uninstall.

    (Full state-matrix coverage lives in tests/test_pawnio_check.py.)"""

    def test_returns_true_when_service_key_exists(self):
        import winreg
        from src.utils.pawnio_check import is_pawnio_service_registered, _PAWNIO_SERVICE_KEY
        with patch("winreg.OpenKey") as mock_open:
            mock_open.return_value.__enter__ = lambda s: s
            mock_open.return_value.__exit__ = MagicMock(return_value=False)
            assert is_pawnio_service_registered() is True
            mock_open.assert_called_once_with(winreg.HKEY_LOCAL_MACHINE, _PAWNIO_SERVICE_KEY)

    def test_returns_false_when_service_key_missing(self):
        from src.utils.pawnio_check import is_pawnio_service_registered
        with patch("winreg.OpenKey", side_effect=FileNotFoundError):
            assert is_pawnio_service_registered() is False

    def test_checks_services_not_uninstall(self):
        """Key must be under SYSTEM\\CurrentControlSet\\Services, never Uninstall."""
        from src.utils.pawnio_check import _PAWNIO_SERVICE_KEY
        assert "Services" in _PAWNIO_SERVICE_KEY
        assert "Uninstall" not in _PAWNIO_SERVICE_KEY


def test_ownership_snapshot_uses_service_registered_not_usable():
    """Ownership (pawnio_was_preinstalled) MUST use is_pawnio_service_registered,
    NOT is_pawnio_usable: a half-state box (registered+running, lib missing) reads
    usable=False, which would make lil_bro wrongly claim a 3rd-party driver and
    remove it on exit (install/uninstall thrash). See plan §B / DA HIGH-4."""
    import pathlib
    for rel in ("src/gui/app.py", "src/main.py"):
        src = pathlib.Path(rel).read_text(encoding="utf-8")
        assert "pawnio_was_preinstalled = is_pawnio_service_registered()" in src
        assert "pawnio_was_preinstalled = is_pawnio_usable()" not in src


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
             patch("src.pipeline.post_run_cleanup.action_logger") as mock_log, \
             patch("subprocess.run") as mock_run:
            _uninstall_pawnio()
            mock_run.assert_not_called()
            # The skip is now logged instead of returning silently.
            assert mock_log.log_action.called

    def test_skips_when_nothing_to_clean(self):
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_not_found = self._make_sc_result(1060)
        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_setup_exe", return_value=None), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_oem_inf", return_value=None), \
             patch("src.pipeline.post_run_cleanup.clear_pawnio_owned_marker") as mock_clear, \
             patch("src.pipeline.post_run_cleanup.action_logger"), \
             patch("subprocess.run", return_value=sc_not_found) as mock_run:
            _uninstall_pawnio()
            # Only _pawnio_service_exists() should be called (returns not-found -> early exit)
            assert mock_run.call_count == 1
            # A stale ownership marker is dropped when nothing is installed.
            mock_clear.assert_called_once()

    def test_skips_third_party_when_preinstalled_no_marker(self):
        """was_preinstalled + no current-boot marker -> leave driver, log skip, no removal."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 4  RUNNING")
        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("src.pipeline.post_run_cleanup.marker_is_current_boot", return_value=False), \
             patch("src.pipeline.post_run_cleanup.clear_pawnio_owned_marker"), \
             patch("src.pipeline.post_run_cleanup.action_logger") as mock_log, \
             patch("subprocess.run", return_value=sc_found) as mock_run:
            _uninstall_pawnio(was_preinstalled=True)
            # Only the existence probe runs; no stop / -uninstall / delete.
            assert mock_run.call_count == 1
            logged = " ".join(str(c.args) for c in mock_log.log_action.call_args_list)
            assert "not installed by lil_bro" in logged

    def test_removes_when_preinstalled_but_current_boot_marker(self):
        """was_preinstalled + same-boot marker -> our leftover -> proceed to removal."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 1  STOPPED")
        setup_ok = self._make_sc_result(0)

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "pawnio_setup" in str(cmd[0]):
                return setup_ok
            return sc_found

        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("src.pipeline.post_run_cleanup.marker_is_current_boot", return_value=True), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_setup_exe",
                   return_value="C:/fake/pawnio_setup.exe"), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_oem_inf", return_value=None), \
             patch("src.pipeline.post_run_cleanup.clear_pawnio_owned_marker") as mock_clear, \
             patch("src.pipeline.post_run_cleanup.action_logger"), \
             patch("subprocess.run", side_effect=side_effect), \
             patch("time.sleep"):
            _uninstall_pawnio(was_preinstalled=True)
            # Fully removed (sc delete rc 0) -> marker cleared.
            mock_clear.assert_called_once()

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
             patch("src.pipeline.post_run_cleanup.clear_pawnio_owned_marker"), \
             patch("src.pipeline.post_run_cleanup.action_logger"), \
             patch("subprocess.run", side_effect=side_effect), \
             patch("time.sleep"):
            _uninstall_pawnio()

        assert "stop" in call_order, "sc stop was not called"
        assert "-uninstall" in call_order, "pawnio_setup.exe -uninstall was not called"
        assert call_order.index("stop") < call_order.index("-uninstall"), \
            "sc stop must precede -uninstall"

    def test_marked_for_deletion_retains_marker(self):
        """sc delete 1072 (pending reboot) must NOT clear the ownership marker."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 1  STOPPED")
        sc_delete_1072 = self._make_sc_result(1072)
        setup_fail = self._make_sc_result(1)

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "pawnio_setup" in str(cmd[0]):
                return setup_fail
            if len(cmd) > 1 and cmd[1] == "delete":
                return sc_delete_1072
            return sc_found

        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_setup_exe",
                   return_value="C:/fake/pawnio_setup.exe"), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_oem_inf", return_value="oem99.inf"), \
             patch("src.pipeline.post_run_cleanup._run_pnputil", return_value=True), \
             patch("src.pipeline.post_run_cleanup.clear_pawnio_owned_marker") as mock_clear, \
             patch("src.pipeline.post_run_cleanup.action_logger"), \
             patch("subprocess.run", side_effect=side_effect), \
             patch("time.sleep"):
            _uninstall_pawnio()
            mock_clear.assert_not_called()

    def test_marked_for_deletion_warns_reboot(self):
        """§F: sc delete 1072 must warn the user to reboot before relaunching, else
        they re-enter the running-service-without-lib half-state (no CPU temps)."""
        from src.pipeline.post_run_cleanup import _uninstall_pawnio
        sc_found = self._make_sc_result(0, "STATE              : 1  STOPPED")
        sc_delete_1072 = self._make_sc_result(1072)
        setup_ok = self._make_sc_result(0)

        def side_effect(*args, **kwargs):
            cmd = args[0]
            if "pawnio_setup" in str(cmd[0]):
                return setup_ok
            if len(cmd) > 1 and cmd[1] == "delete":
                return sc_delete_1072
            return sc_found

        with patch("src.pipeline.post_run_cleanup.is_admin", return_value=True), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_setup_exe",
                   return_value="C:/fake/pawnio_setup.exe"), \
             patch("src.pipeline.post_run_cleanup._find_pawnio_oem_inf", return_value=None), \
             patch("src.pipeline.post_run_cleanup.clear_pawnio_owned_marker"), \
             patch("src.pipeline.post_run_cleanup.action_logger") as mock_log, \
             patch("src.utils.formatting.print_warning") as mock_warn, \
             patch("subprocess.run", side_effect=side_effect), \
             patch("time.sleep"):
            _uninstall_pawnio()
            warned = " ".join(str(c) for c in mock_warn.call_args_list).lower()
            assert "reboot" in warned
            logged = " ".join(str(c.args) for c in mock_log.log_action.call_args_list).lower()
            assert "reboot required" in logged


# ---------------------------------------------------------------------------
# pawnio_ownership — cross-run ownership marker + boot-session gating
# ---------------------------------------------------------------------------

class TestPawnioOwnership:

    def test_mark_read_clear_roundtrip(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src.utils.pawnio_ownership import (
            mark_pawnio_owned, read_pawnio_owned_marker, clear_pawnio_owned_marker,
        )
        assert read_pawnio_owned_marker() is None
        mark_pawnio_owned()
        marker = read_pawnio_owned_marker()
        assert marker is not None
        assert marker["installed_by"] == "lil_bro"
        assert "installed_at" in marker
        clear_pawnio_owned_marker()
        assert read_pawnio_owned_marker() is None

    def test_clear_is_noop_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src.utils.pawnio_ownership import clear_pawnio_owned_marker
        clear_pawnio_owned_marker()  # must not raise

    def test_read_returns_none_on_garbage(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        from src.utils.pawnio_ownership import (
            read_pawnio_owned_marker, get_pawnio_owned_marker_path,
        )
        get_pawnio_owned_marker_path().write_text("not json{", encoding="utf-8")
        assert read_pawnio_owned_marker() is None

    def test_current_boot_true_when_marker_after_boot(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta
        monkeypatch.chdir(tmp_path)
        import src.utils.pawnio_ownership as po
        po.mark_pawnio_owned()
        # Boot was an hour ago; marker written 'now' -> current boot.
        monkeypatch.setattr(po, "_last_boot_time", lambda: datetime.now() - timedelta(hours=1))
        assert po.marker_is_current_boot() is True

    def test_current_boot_false_when_marker_predates_boot(self, tmp_path, monkeypatch):
        from datetime import datetime, timedelta
        monkeypatch.chdir(tmp_path)
        import src.utils.pawnio_ownership as po
        po.mark_pawnio_owned()
        # Boot is in the future relative to the marker -> stale -> not current boot.
        monkeypatch.setattr(po, "_last_boot_time", lambda: datetime.now() + timedelta(hours=1))
        assert po.marker_is_current_boot() is False

    def test_current_boot_false_when_absent(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        import src.utils.pawnio_ownership as po
        assert po.marker_is_current_boot() is False


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

    def test_logs_fail_when_rmtree_locked(self, tmp_path, monkeypatch):
        """A locked _MEI dir (OSError) must be logged, not silently swallowed."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        orphan = tmp_path / "_MEI123456"
        orphan.mkdir()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup.action_logger") as mock_logger, \
             patch("shutil.rmtree", side_effect=OSError("tools locked by cmd")):
            _cleanup_stale_mei()  # must not raise; loop continues past the failure
        outcomes = [kw.get("outcome") for _, kw in mock_logger.log_action.call_args_list]
        messages = [a[1] for a, _ in mock_logger.log_action.call_args_list]
        assert "FAIL" in outcomes
        assert any("Failed to remove stale PyInstaller dir" in m for m in messages)

    def test_at_startup_logs_warn_before_removal(self, tmp_path, monkeypatch):
        """At boot, a leftover _MEI must be logged WARN *before* it is removed."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        orphan = tmp_path / "_MEI123456"
        orphan.mkdir()
        (orphan / "tools").mkdir()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup.action_logger") as mock_logger:
            _cleanup_stale_mei(at_startup=True)
        # The orphan is gone …
        assert not orphan.exists()
        # … and a WARN attributing it to the prior run's bootloader fired before
        # the "Removed stale PyInstaller dir" entry.
        messages = [a[1] for a, _ in mock_logger.log_action.call_args_list]
        outcomes = [kw.get("outcome") for _, kw in mock_logger.log_action.call_args_list]
        assert "WARN" in outcomes
        warn_idx = next(
            i for i, m in enumerate(messages) if "Previous run left a temp dir" in m
        )
        removed_idx = next(
            i for i, m in enumerate(messages) if "Removed stale PyInstaller dir" in m
        )
        assert warn_idx < removed_idx, "WARN must be logged before removal"

    def test_at_startup_no_mei_logs_no_warn(self, tmp_path, monkeypatch):
        """At boot with no _MEI dirs, no WARN is logged and nothing raises."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        (tmp_path / "somefile.txt").touch()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup.action_logger") as mock_logger:
            _cleanup_stale_mei(at_startup=True)  # must not raise
        messages = [a[1] for a, _ in mock_logger.log_action.call_args_list]
        assert not any("Previous run left a temp dir" in m for m in messages)

    def test_default_sweep_does_not_log_warn(self, tmp_path, monkeypatch):
        """The exit-time sweep (at_startup=False) must not emit the boot WARN."""
        from src.pipeline.post_run_cleanup import _cleanup_stale_mei
        orphan = tmp_path / "_MEI222222"
        orphan.mkdir()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup.action_logger") as mock_logger:
            _cleanup_stale_mei()  # default at_startup=False
        messages = [a[1] for a, _ in mock_logger.log_action.call_args_list]
        assert not any("Previous run left a temp dir" in m for m in messages)

    def test_orphaned_mei_at_startup_noop_when_empty(self, tmp_path, monkeypatch):
        """Public wrapper is a no-op that never raises when CWD has no _MEI dirs."""
        from src.pipeline.post_run_cleanup import cleanup_orphaned_mei_at_startup
        monkeypatch.chdir(tmp_path)
        cleanup_orphaned_mei_at_startup()  # must not raise

    def test_orphaned_mei_at_startup_skips_current_meipass(self, tmp_path, monkeypatch):
        """Public wrapper logs+removes orphans but never the current _MEIPASS."""
        from src.pipeline.post_run_cleanup import cleanup_orphaned_mei_at_startup
        our_mei = tmp_path / "_MEI999999"
        our_mei.mkdir()
        other_mei = tmp_path / "_MEI111111"
        other_mei.mkdir()
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("sys._MEIPASS", str(our_mei), raising=False)
        with patch("src.pipeline.post_run_cleanup.action_logger") as mock_logger:
            cleanup_orphaned_mei_at_startup()
        assert our_mei.exists(), "Must not delete current process _MEIPASS"
        assert not other_mei.exists(), "Must remove orphaned _MEI dirs"
        messages = [a[1] for a, _ in mock_logger.log_action.call_args_list]
        assert any("Previous run left a temp dir" in m for m in messages)


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

    def test_logs_fail_when_rmtree_locked(self, tmp_path, monkeypatch):
        """A locked dir (OSError) must be logged, not silently swallowed."""
        from src.pipeline.post_run_cleanup import _cleanup_cwd_tempdir
        lil_bro_dir = tmp_path / "lil_bro"
        lil_bro_dir.mkdir()
        monkeypatch.chdir(tmp_path)
        with patch("src.pipeline.post_run_cleanup.action_logger") as mock_logger, \
             patch("shutil.rmtree", side_effect=OSError("dir locked")):
            _cleanup_cwd_tempdir()  # must not raise
        outcomes = [kw.get("outcome") for _, kw in mock_logger.log_action.call_args_list]
        messages = [a[1] for a, _ in mock_logger.log_action.call_args_list]
        assert "FAIL" in outcomes
        assert any("Failed to remove runtime temp dir" in m for m in messages)


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

    def test_mei_handoff_note_logged_when_frozen(self, monkeypatch):
        """Frozen build: shutdown logs the _MEI hand-off note (honest — not 'removed')."""
        import sys
        from src.pipeline import post_run_cleanup as prc
        monkeypatch.setattr(sys, "_MEIPASS", "C:/fake/_MEI123456", raising=False)
        with patch.object(prc, "_uninstall_pawnio"), \
             patch.object(prc, "_cleanup_cwd_tempdir"), \
             patch.object(prc, "_cleanup_stale_mei"), \
             patch.object(prc, "action_logger") as mock_log, \
             patch.object(prc, "print_info"), \
             patch.object(prc, "print_dim"):
            prc.post_run_cleanup(lhm=None)
        logged = " ".join(str(c.args) for c in mock_log.log_action.call_args_list)
        assert "handed to bootloader for removal on exit" in logged

    def test_mei_handoff_note_absent_in_dev_mode(self, monkeypatch):
        """Dev mode (no _MEIPASS): no hand-off note — nothing to hand off."""
        import sys
        from src.pipeline import post_run_cleanup as prc
        monkeypatch.delattr(sys, "_MEIPASS", raising=False)
        with patch.object(prc, "_uninstall_pawnio"), \
             patch.object(prc, "_cleanup_cwd_tempdir"), \
             patch.object(prc, "_cleanup_stale_mei"), \
             patch.object(prc, "action_logger") as mock_log, \
             patch.object(prc, "print_info"), \
             patch.object(prc, "print_dim"):
            prc.post_run_cleanup(lhm=None)
        logged = " ".join(str(c.args) for c in mock_log.log_action.call_args_list)
        assert "handed to bootloader" not in logged
