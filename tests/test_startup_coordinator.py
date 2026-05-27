"""Tests for src.gui.startup_coordinator.StartupCoordinator.

Focused on the dashboard monitor-fix guards (CR-1, CR-2) that prevent the
session-manifest corruption modes uncovered during /review:

- CR-1: a fix triggered from the Dashboard while the optimization pipeline is
  already running races ApplyPhase's own _fix_display() -- both call
  ChangeDisplaySettingsExW and both append a manifest entry, so the second
  entry's "before" state is whatever the first wrote, breaking revert.
- CR-2: a rapid double-click would spawn two _MonitorFixWorker QThreads with
  identical filtered_specs; the second's "before" entry is the first's after.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.gui.startup_coordinator import StartupCoordinator


def _make_coordinator(runtime: dict | None = None) -> StartupCoordinator:
    """Build a StartupCoordinator with the minimum mocks needed for the guards."""
    main = MagicMock()
    main._dashboard = MagicMock()
    log = MagicMock()
    orchestrator = MagicMock()
    pipeline = MagicMock()
    return StartupCoordinator(
        main=main,
        runtime=runtime if runtime is not None else {},
        log=log,
        orchestrator=orchestrator,
        pipeline=pipeline,
    )


class TestMonitorFixGuards:
    def test_suppressed_when_pipeline_thread_set(self):
        """CR-1: a fix request while pipeline_thread is set must be dropped before
        any worker is spawned and before any dialog is shown."""
        runtime = {
            "pipeline_thread": MagicMock(),
            "preloaded_specs": {
                "DisplayCapabilities": [{"device": r"\\.\DISPLAY1"}]
            },
        }
        coord = _make_coordinator(runtime)
        with patch("src.gui.worker._MonitorFixWorker") as mock_worker, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread, \
             patch("src.gui.widgets.batch_selection_dialog.BatchSelectionDialog") as mock_dialog:
            coord.on_monitor_fix_requested(r"\\.\DISPLAY1")
        mock_worker.assert_not_called()
        mock_thread.assert_not_called()
        mock_dialog.assert_not_called()
        assert "monitor_fix_thread" not in runtime
        coord._log.warning.assert_called_once()
        msg = coord._log.warning.call_args[0][0]
        assert "pipeline" in msg.lower()

    def test_suppressed_when_monitor_fix_thread_set(self):
        """CR-2: a second click while monitor_fix_thread is set must be dropped."""
        sentinel_thread = MagicMock()
        runtime = {
            "monitor_fix_thread": sentinel_thread,
            "preloaded_specs": {
                "DisplayCapabilities": [{"device": r"\\.\DISPLAY1"}]
            },
        }
        coord = _make_coordinator(runtime)
        with patch("src.gui.worker._MonitorFixWorker") as mock_worker, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread, \
             patch("src.gui.widgets.batch_selection_dialog.BatchSelectionDialog") as mock_dialog:
            coord.on_monitor_fix_requested(r"\\.\DISPLAY1")
        mock_worker.assert_not_called()
        mock_thread.assert_not_called()
        mock_dialog.assert_not_called()
        # Pre-existing sentinel must not be touched.
        assert runtime["monitor_fix_thread"] is sentinel_thread
        coord._log.warning.assert_called_once()
        msg = coord._log.warning.call_args[0][0]
        assert "already in progress" in msg.lower()

    def test_unknown_device_still_returns_early(self):
        """Negative-path baseline: when neither guard fires, the existing
        unknown-device guard at the bottom of the resolver still works."""
        runtime = {"preloaded_specs": {"DisplayCapabilities": []}}
        coord = _make_coordinator(runtime)
        with patch("src.gui.worker._MonitorFixWorker") as mock_worker, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread:
            coord.on_monitor_fix_requested(r"\\.\DISPLAY1")
        mock_worker.assert_not_called()
        mock_thread.assert_not_called()
        coord._log.warning.assert_called_once()
        msg = coord._log.warning.call_args[0][0]
        assert "unknown device" in msg.lower()



class TestRefreshMonitorCard:
    """C10 (E1): refresh_monitor_card runs get_monitor_refresh_capabilities
    on a worker thread so the 200-800ms EnumDisplayDevicesW + WMI fallback
    doesn't jank the GUI."""

    def test_dispatches_worker_off_main_thread(self):
        """A first call spawns a worker + thread and registers them on runtime."""
        runtime: dict = {}
        coord = _make_coordinator(runtime)
        with patch("src.gui.worker._MonitorRefreshWorker") as mock_worker_cls, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread_cls:
            coord.refresh_monitor_card()
        mock_worker_cls.assert_called_once_with()
        mock_thread_cls.assert_called_once_with()
        assert runtime.get("monitor_refresh_thread") is mock_thread_cls.return_value
        assert runtime.get("monitor_refresh_worker") is mock_worker_cls.return_value
        # The worker's run slot must be wired to thread.started so the OS
        # event loop kicks it off when start() is called.
        mock_thread_cls.return_value.started.connect.assert_called_with(
            mock_worker_cls.return_value.run
        )
        mock_thread_cls.return_value.start.assert_called_once()

    def test_second_call_is_dropped_while_in_flight(self):
        """A second click while a refresh is already running must NOT spawn
        a second worker -- the in-flight one will deliver the result."""
        sentinel_thread = MagicMock()
        runtime = {"monitor_refresh_thread": sentinel_thread}
        coord = _make_coordinator(runtime)
        with patch("src.gui.worker._MonitorRefreshWorker") as mock_worker_cls, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread_cls:
            coord.refresh_monitor_card()
        mock_worker_cls.assert_not_called()
        mock_thread_cls.assert_not_called()
        assert runtime["monitor_refresh_thread"] is sentinel_thread

    def test_result_handler_updates_dashboard_and_specs(self):
        """The finished(list) signal handler writes back to the dashboard
        and to runtime['preloaded_specs']."""
        runtime: dict = {"preloaded_specs": {"PowerPlan": {"name": "High"}}}
        coord = _make_coordinator(runtime)
        displays = [{"device": r"\\.\DISPLAY1", "current_refresh_hz": 144, "max_refresh_hz": 144}]
        coord._on_refresh_result(displays)
        coord._main._dashboard.set_monitor_data.assert_called_once_with(displays)
        # preloaded_specs is updated in place; existing keys preserved.
        assert runtime["preloaded_specs"]["DisplayCapabilities"] == displays
        assert runtime["preloaded_specs"]["PowerPlan"] == {"name": "High"}

    def test_failed_handler_logs_warning(self):
        """The failed(str) signal handler logs and is otherwise a no-op --
        the empty-card state stays whatever it was before the refresh."""
        coord = _make_coordinator({})
        coord._on_refresh_failed("EnumDisplayDevicesW returned 0")
        coord._log.warning.assert_called_once()
