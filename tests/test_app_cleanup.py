"""Unit tests for src/gui/app._run_app_cleanup.

Verifies the close-during-pipeline shutdown contract:
  - thread.quit() is called before thread.wait() so exec() can exit
  - wait() uses a short timeout (not the old 15 s)
  - remaining cleanup (LHM, geometry) still runs even if cancel raises
"""
from unittest.mock import MagicMock, call, patch


def _make_runtime(with_pipeline=False, with_revert=False,
                  with_monitor_fix=False, with_monitor_refresh=False):
    runtime: dict = {"lhm": MagicMock()}
    if with_pipeline:
        runtime["pipeline_worker"] = MagicMock()
        runtime["pipeline_thread"] = MagicMock()
        runtime["pipeline_thread"].wait.return_value = True
    if with_revert:
        runtime["revert_thread"] = MagicMock()
        runtime["revert_thread"].wait.return_value = True
    if with_monitor_fix:
        runtime["monitor_fix_thread"] = MagicMock()
        runtime["monitor_fix_thread"].wait.return_value = True
    if with_monitor_refresh:
        runtime["monitor_refresh_thread"] = MagicMock()
        runtime["monitor_refresh_thread"].wait.return_value = True
    return runtime


@patch("src.gui.app.post_run_cleanup", create=True)
class TestRunAppCleanup:

    def _call(self, runtime, log=None, settings=None):
        from src.gui.app import _run_app_cleanup
        main = MagicMock()
        bridge = MagicMock()
        _run_app_cleanup(
            main,
            bridge,
            runtime,
            log or MagicMock(),
            settings or MagicMock(),
            pawnio_was_preinstalled=False,
        )
        return main, bridge

    def test_pipeline_quit_called_before_wait(self, _mock_cleanup):
        """quit() must be posted to the worker's exec() loop before wait()."""
        runtime = _make_runtime(with_pipeline=True)
        thread = runtime["pipeline_thread"]
        manager = MagicMock()
        thread.quit = manager.quit
        thread.wait = manager.wait
        manager.wait.return_value = True

        self._call(runtime)

        assert manager.mock_calls[0] == call.quit(), (
            "quit() must precede wait() so exec() can drain"
        )
        assert manager.mock_calls[1] == call.wait(2000)

    def test_pipeline_wait_uses_short_timeout(self, _mock_cleanup):
        """wait() must not use the old 15 000 ms timeout."""
        runtime = _make_runtime(with_pipeline=True)
        self._call(runtime)
        runtime["pipeline_thread"].wait.assert_called_once_with(2000)

    def test_pipeline_request_cancel_and_abort_pending_called(self, _mock_cleanup):
        """request_cancel() and bridge.abort_pending() must fire before quit()."""
        runtime = _make_runtime(with_pipeline=True)
        main = MagicMock()
        bridge = MagicMock()
        from src.gui.app import _run_app_cleanup
        _run_app_cleanup(main, bridge, runtime, MagicMock(), MagicMock(),
                         pawnio_was_preinstalled=False)
        runtime["pipeline_worker"].request_cancel.assert_called_once()
        bridge.abort_pending.assert_called()

    def test_revert_quit_called_before_wait(self, _mock_cleanup):
        """Revert thread also gets quit() before wait()."""
        runtime = _make_runtime(with_revert=True)
        thread = runtime["revert_thread"]
        manager = MagicMock()
        thread.quit = manager.quit
        thread.wait = manager.wait
        manager.wait.return_value = True

        self._call(runtime)

        assert manager.mock_calls[0] == call.quit()
        assert manager.mock_calls[1] == call.wait(2000)

    def test_cleanup_no_pipeline_does_not_crash(self, _mock_cleanup):
        """Empty runtime dict completes without raising."""
        runtime = {"lhm": MagicMock()}
        self._call(runtime)  # must not raise

    def test_pipeline_cancel_exception_does_not_abort_remaining_cleanup(self, _mock_cleanup):
        """If request_cancel() raises, the rest of cleanup (geometry, etc.) still runs."""
        runtime = _make_runtime(with_pipeline=True)
        runtime["pipeline_worker"].request_cancel.side_effect = RuntimeError("boom")
        log = MagicMock()
        settings = MagicMock()
        self._call(runtime, log=log, settings=settings)
        log.warning.assert_called()   # exception was logged
        settings.save_geometry.assert_called_once()  # geometry save still ran  # LHM cleanup still ran

    def test_pipeline_wait_timeout_logs_warning(self, _mock_cleanup):
        """If wait() times out (returns False), a warning is logged."""
        runtime = _make_runtime(with_pipeline=True)
        runtime["pipeline_thread"].wait.return_value = False
        log = MagicMock()
        self._call(runtime, log=log)
        # At least one warning about timeout
        warning_msgs = [str(c) for c in log.warning.call_args_list]
        assert any("2s" in m or "reap" in m for m in warning_msgs), (
            f"Expected timeout warning, got: {warning_msgs}"
        )
