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
