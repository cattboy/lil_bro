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

from PySide6.QtCore import QObject, QThread

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
        """CR-2: a second fix request while card_fix_in_progress is set must be dropped."""
        runtime = {
            "card_fix_in_progress": True,
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
        # Gate must not be cleared by a suppressed request.
        assert runtime["card_fix_in_progress"] is True
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


    def test_refresh_suppressed_when_pipeline_thread_set(self):
        """A refresh while the pipeline is running would mutate
        runtime['preloaded_specs'] (which can alias the live ctx.specs in
        the scan-fallback path), so we drop the click. Same shape of bug
        as CR-1 for on_monitor_fix_requested."""
        runtime = {"pipeline_thread": MagicMock()}
        coord = _make_coordinator(runtime)
        with patch("src.gui.worker._MonitorRefreshWorker") as mock_worker_cls, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread_cls:
            coord.refresh_monitor_card()
        mock_worker_cls.assert_not_called()
        mock_thread_cls.assert_not_called()
        assert "monitor_refresh_thread" not in runtime
        coord._log.warning.assert_called_once()
        msg = coord._log.warning.call_args[0][0]
        assert "pipeline" in msg.lower()

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


class TestQObjectThreadAnchoring:
    """Regression for the dashboard-lock + dirty-exit bug.

    The card-fix worker QThreads emit ``finished``/``result`` from the worker
    thread, so their cleanup slots must be delivered on the GUI thread. That
    needs (1) the coordinator to be a ``QObject`` (anchors its bound-method
    slots to the main thread) and (2) the cleanup to be a bound method, not a
    bare lambda (which PySide6 cannot anchor cross-thread). Before the fix the
    ``card_fix_in_progress`` guard was stranded ``True`` and the dashboard
    locked; the mocked-``QThread`` tests above never exercised real delivery.
    """

    def test_coordinator_is_a_qobject(self):
        # Without a QObject receiver PySide6 falls back to DirectConnection on
        # the emitting (worker) thread -- the root cause of the stranded guard.
        assert issubclass(StartupCoordinator, QObject)

    def test_thread_finished_cleanups_are_bound_methods(self):
        coord = _make_coordinator({})
        for name in (
            "_on_monitor_fix_thread_finished",
            "_on_nvidia_fix_thread_finished",
            "_on_refresh_thread_finished",
            "_on_thermal_retry_thread_finished",
        ):
            slot = getattr(coord, name)
            # A bound method has __self__ == the coordinator; a lambda does not.
            # Locks in the "no bare lambda" contract the anchoring relies on.
            assert getattr(slot, "__self__", None) is coord

    def test_monitor_fix_cleanup_clears_all_runtime_keys(self):
        runtime = {
            "card_fix_in_progress": True,
            "restore_point_in_progress": True,
            "monitor_fix_thread": MagicMock(),
            "monitor_fix_worker": MagicMock(),
        }
        coord = _make_coordinator(runtime)
        coord._on_monitor_fix_thread_finished()
        for key in (
            "card_fix_in_progress",
            "restore_point_in_progress",
            "monitor_fix_thread",
            "monitor_fix_worker",
        ):
            assert key not in runtime

    def test_cleanup_delivered_across_real_worker_thread(self, qtbot):
        """End-to-end: wire the real cleanup slot to a real ``QThread.finished``
        (emitted from the worker thread) exactly as ``on_monitor_fix_requested``
        does, and confirm the guard clears once the queued slot is delivered on
        the GUI thread. Red on the pre-fix code (non-QObject + bare lambda);
        green after."""
        runtime = {"card_fix_in_progress": True}
        coord = _make_coordinator(runtime)

        thread = QThread()
        thread.finished.connect(coord._on_monitor_fix_thread_finished)
        thread.started.connect(thread.quit)  # default run()==exec(); quit emits finished

        with qtbot.waitSignal(thread.finished, timeout=3000):
            thread.start()
        # The cleanup is a queued event delivered AFTER finished; pump until it runs.
        qtbot.waitUntil(lambda: "card_fix_in_progress" not in runtime, timeout=3000)
        thread.wait()

        assert "card_fix_in_progress" not in runtime


class TestManifestSignatureGuard:
    """The Applied Fixes watcher (T-016) now watches the busy CWD root, so
    _on_backups_changed reloads only when the manifest's (mtime_ns, size)
    signature actually changes -- unrelated CWD churn (log writes, _MEI* and
    ./lil_bro/ temp dirs) costs one os.stat, never a reload."""

    def test_manifest_sig_returns_mtime_size_when_present(self, tmp_path):
        manifest = tmp_path / "lil_bro_session_manifest.json"
        manifest.write_text("{}")
        coord = _make_coordinator({})
        with patch("src.utils.paths.get_session_backup_path", return_value=manifest):
            sig = coord._manifest_sig()
        st = manifest.stat()
        assert sig == (st.st_mtime_ns, st.st_size)

    def test_manifest_sig_returns_none_when_absent(self, tmp_path):
        missing = tmp_path / "nope.json"
        coord = _make_coordinator({})
        with patch("src.utils.paths.get_session_backup_path", return_value=missing):
            assert coord._manifest_sig() is None

    def test_backups_changed_skips_reload_when_signature_unchanged(self):
        """Unrelated CWD activity: signature unchanged -> no debounce, no reload."""
        coord = _make_coordinator({})
        coord._last_run_watcher = None  # skip the defensive re-add branch
        coord._last_run_debounce = MagicMock()
        coord._last_manifest_sig = (111, 222)
        with patch.object(coord, "_manifest_sig", return_value=(111, 222)):
            coord._on_backups_changed("/cwd")
        coord._last_run_debounce.start.assert_not_called()

    def test_backups_changed_reloads_when_signature_changed(self):
        """A real manifest write (or delete) changes the signature -> reload."""
        coord = _make_coordinator({})
        coord._last_run_watcher = None
        coord._last_run_debounce = MagicMock()
        coord._last_manifest_sig = (111, 222)
        with patch.object(coord, "_manifest_sig", return_value=(333, 444)):
            coord._on_backups_changed("/cwd")
        coord._last_run_debounce.start.assert_called_once()
        assert coord._last_manifest_sig == (333, 444)


class TestRefreshFixCardsAfterRevert:
    """refresh_fix_cards_after_revert re-scans the NVIDIA + monitor fix cards so a
    revert drops the optimistic 'applied' state set at apply time (the post-revert
    staleness bug). Routed here from RevertWorker.revert_finished on the GUI thread."""

    def test_rescans_nvidia_and_monitor(self):
        runtime = {"preloaded_specs": {"NVIDIA": [{"GPU": "RTX 4080"}]}}
        coord = _make_coordinator(runtime)
        sentinel = {"status": "WARNING", "current": {}, "expected": {}}
        with patch(
            "src.agent_tools.nvidia_profile.analyze_nvidia_profile",
            return_value=sentinel,
        ) as mock_analyze, \
             patch("src.gui.worker._MonitorRefreshWorker"), \
             patch("src.gui.startup_coordinator.QThread") as mock_thread_cls:
            coord.refresh_fix_cards_after_revert()
        # NVIDIA card re-scanned with the fresh analysis of the cached specs.
        mock_analyze.assert_called_once_with(runtime["preloaded_specs"])
        coord._main._dashboard.set_nvidia_profile_findings.assert_called_once_with(sentinel)
        # Monitor card re-probed live (refresh_monitor_card spawned its worker thread).
        mock_thread_cls.return_value.start.assert_called_once()

    def test_noop_when_pipeline_running(self):
        runtime = {
            "pipeline_thread": MagicMock(),
            "preloaded_specs": {"NVIDIA": [{"GPU": "RTX 4080"}]},
        }
        coord = _make_coordinator(runtime)
        with patch(
            "src.agent_tools.nvidia_profile.analyze_nvidia_profile",
        ) as mock_analyze, \
             patch("src.gui.worker._MonitorRefreshWorker") as mock_worker_cls, \
             patch("src.gui.startup_coordinator.QThread") as mock_thread_cls:
            coord.refresh_fix_cards_after_revert()
        mock_analyze.assert_not_called()
        coord._main._dashboard.set_nvidia_profile_findings.assert_not_called()
        mock_worker_cls.assert_not_called()
        mock_thread_cls.assert_not_called()
