"""Startup orchestration coordinator for the GUI.

Extracted from ``app.run()``'s closure: owns the StartupOrchestrator
step / lhm-ready / finished handlers and the monitor-refresh-card
handlers. ``app.run()`` constructs one instance and routes the
orchestrator + dashboard signals to its methods.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Slot


class StartupCompleter(QObject):
    """Hosts an orchestrator slot on the main thread.

    PySide6 cannot reliably route a QueuedConnection to a bare callable -- the
    queued event needs a QObject receiver to anchor it to a thread's event
    loop. Wrapping the slot in a QObject parented to ``main`` guarantees
    main-thread delivery.
    """

    def __init__(self, on_done, parent=None) -> None:
        super().__init__(parent)
        self._on_done = on_done

    @Slot(object)
    def on_finished(self, startup_lhm) -> None:
        self._on_done(startup_lhm)


class StartupCoordinator:
    """Owns the StartupOrchestrator + monitor-refresh-card signal handlers.

    Constructed once by ``app.run()``; the shared ``runtime`` dict is stored
    by reference. ``pipeline`` is the PipelineController -- ``on_finished``
    re-enables the flow controls through it once startup completes.
    """

    def __init__(self, main, runtime: dict, log, orchestrator, pipeline) -> None:
        self._main = main
        self._runtime = runtime
        self._log = log
        self._orchestrator = orchestrator
        self._pipeline = pipeline
        # Applied Fixes card (T-016): a QFileSystemWatcher refreshes it live; a
        # single-shot QTimer debounces the double directoryChanged per write.
        self._last_run_watcher = None
        self._last_run_debounce = None
        self._last_manifest_sig = None
        self._init_last_run_watcher()

    # ── Applied Fixes card (T-016) ──────────────────────────────────────

    def _manifest_sig(self) -> tuple[int, int] | None:
        """Change signature of the session manifest: ``(st_mtime_ns, st_size)``.

        Returns None when the manifest is absent. The manifest's parent is the
        busy CWD root, so ``_on_backups_changed`` compares this signature to
        suppress reloads triggered by unrelated activity (log writes, ``_MEI*``
        and ``./lil_bro/`` temp dirs) -- only a real manifest write or delete
        changes it.
        """
        from src.utils.paths import get_session_backup_path
        try:
            st = get_session_backup_path().stat()
        except OSError:
            return None
        return (st.st_mtime_ns, st.st_size)

    def _init_last_run_watcher(self) -> None:
        """Watch the CWD root so the Applied Fixes card refreshes on every manifest
        write (a fix) or delete (a revert).

        The manifest now lives at the CWD root (``lil_bro_session_manifest.json``),
        beside the logs. We watch the *directory*, not the file: an atomic
        ``os.replace`` swaps the inode and a file-level watch silently stops after
        the first change on Windows. But the CWD root is busy (logs, ``_MEI*``, the
        ``./lil_bro/`` temp dir), so ``_on_backups_changed`` guards every event
        against a cheap manifest signature (mtime+size) -- unrelated churn costs one
        ``os.stat``, never a reload. Each manifest write fires ``directoryChanged``
        twice (the ``.tmp`` create then the rename), so a 150 ms single-shot timer
        collapses the pair into one reload. Parented to the main window so Qt tears
        it down with it.
        """
        from PySide6.QtCore import QObject

        # Unit tests construct the coordinator with a mock main; the real Qt
        # watcher/timer require a genuine QObject parent. Skip there -- production
        # always passes the MainWindow.
        if not isinstance(self._main, QObject):
            self._log.debug("Applied Fixes watcher skipped: main is not a QObject")
            return
        try:
            from PySide6.QtCore import QFileSystemWatcher, QTimer
            from src.utils.paths import get_session_backup_path

            watch_dir = str(get_session_backup_path().parent)  # CWD root (always exists)
            self._last_manifest_sig = self._manifest_sig()
            self._last_run_debounce = QTimer(self._main)
            self._last_run_debounce.setSingleShot(True)
            self._last_run_debounce.setInterval(150)
            self._last_run_debounce.timeout.connect(self._reload_last_run)

            self._last_run_watcher = QFileSystemWatcher([watch_dir], self._main)
            self._last_run_watcher.directoryChanged.connect(self._on_backups_changed)
        except Exception as exc:
            self._log.warning("Applied Fixes watcher init failed: %s", exc, exc_info=True)

    def _on_backups_changed(self, _path: str) -> None:
        # Some platforms drop the watch after a delete/recreate; re-add defensively.
        try:
            from src.utils.paths import get_session_backup_path
            d = str(get_session_backup_path().parent)
            if self._last_run_watcher is not None and d not in self._last_run_watcher.directories():
                self._last_run_watcher.addPath(d)
        except Exception:
            pass  # best-effort re-add; the signature check below still runs
        # The watched dir is the busy CWD root -- only reload when the manifest
        # itself changed (write or delete), not on unrelated file activity.
        cur = self._manifest_sig()
        if cur == self._last_manifest_sig:
            return
        self._last_manifest_sig = cur
        if self._last_run_debounce is not None:
            self._last_run_debounce.start()

    def _reload_last_run(self) -> None:
        """Re-read the manifest and feed the Applied Fixes card (GUI thread)."""
        try:
            from src.utils.revert import load_manifest
            self._main._revert_view.set_last_run(load_manifest())
        except Exception as exc:
            self._log.warning("Applied Fixes refresh failed: %s", exc, exc_info=True)

    # ── Orchestrator step / completion ─────────────────────────────────

    def on_step(self, name: str, status: str) -> None:
        try:
            self._log.debug("GUI Startup step: %s status=%s", name, status)
            label = (
                f"{name}: failed (continuing)"
                if status == "fail"
                else f"{name}…"
            )
            self._main.status_bar_widget.set_state("run", label)
        except Exception as exc:
            self._log.error("on_step EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

    def on_finished(self, startup_lhm) -> None:
        log = self._log
        runtime = self._runtime
        main = self._main
        log.info(
            "GUI Startup: on_finished entry (lhm=%s)",
            "yes" if startup_lhm else "no",
        )
        runtime["startup_done"] = True
        # Idempotent: on_lhm_ready set this earlier in the success path; here
        # it covers the LHM-failed case where on_lhm_ready was never called.
        runtime["lhm"] = startup_lhm

        # Specs were loaded by StartupOrchestrator Step 3 on the worker
        # thread (see startup.py); reading the attribute here is just a
        # dict reference -- no main-thread file I/O.
        runtime["preloaded_specs"] = getattr(self._orchestrator, "preloaded_specs", {}) or {}

        try:
            if runtime.get("pipeline_thread") is None and runtime.get("revert_thread") is None:
                self._pipeline.set_flow_controls(True)
        except Exception:
            pass  # safe: flow-control restore is best-effort; runtime keys may be missing during shutdown
        try:
            main.status_bar_widget.set_state("ok", "Idle")

            # Defensive fallback: polling normally starts from on_lhm_ready
            # several seconds earlier. If that QueuedConnection didn't deliver
            # for any reason, on_finished is the safety net. start_polling()
            # guards against double-call internally (returns if _worker is set),
            # so this is harmless when the normal path already fired.
            if startup_lhm is not None and main._dashboard._worker is None:
                log.warning(
                    "GUI Startup: lhm_ready slot never delivered -- "
                    "falling back to start_polling from on_finished"
                )
                main._dashboard.start_polling()

            if startup_lhm is None:
                main._dashboard.thermal_chart.set_offline("Thermal monitor unavailable")
        except Exception as exc:
            log.error("on_finished EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

        # Late-fire monitor wiring: if main.show() already ran before this slot
        # fired (slow-path on iGPU machines), wire here. The post-splash block
        # in run() wires on the fast-path. _monitor_wired prevents double-wire.
        if main.isVisible() and not runtime.get("_monitor_wired", False):
            try:
                _specs = runtime.get("preloaded_specs", {}) or {}
                main._dashboard.set_monitor_data(_specs.get("DisplayCapabilities", []))
                main._dashboard.monitor_fix_requested.connect(self.on_monitor_fix_requested)
                main._dashboard.monitor_refresh_requested.connect(self.refresh_monitor_card)
                runtime["_monitor_wired"] = True
                log.info("GUI Startup: monitor card wired (late-fire path)")
            except Exception as exc:
                log.warning("Could not wire monitor card (late path): %s", exc, exc_info=True)

        # Seed the Applied Fixes card (T-016). on_finished fires exactly once per
        # session on both the fast and slow startup paths, so seeding here covers
        # both without editing app.run(). The card is pre-allocated in
        # RevertView.__init__; the QFileSystemWatcher keeps it fresh thereafter.
        # Reuses _reload_last_run -- the same load_manifest + set_last_run path.
        self._reload_last_run()

        log.info("GUI Startup: on_finished exit")

    def on_lhm_ready(self, lhm) -> None:
        """Start dashboard polling the moment LHM is ready (orchestrator Step 1).

        Firing here -- rather than after the whole startup completes -- gives
        the worker ~5-10s of "free" polling time while the splash still shows
        later steps, so cards are populated by splash close.
        """
        log = self._log
        log.info("GUI Startup: lhm_ready received, starting dashboard polling early")
        self._runtime["lhm"] = lhm
        try:
            self._main._dashboard.start_polling()
        except Exception as exc:
            log.error("on_lhm_ready EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

    # ── Monitor refresh card ───────────────────────────────────────────

    def refresh_monitor_card(self) -> None:
        """Re-probe monitor capabilities on a worker thread.

        get_monitor_refresh_capabilities() runs EnumDisplayDevicesW + an
        optional WMI fallback, blocking for 200-800 ms. Doing that on the
        GUI thread janks the dashboard when the user clicks Refresh or
        when this fires off fix_thread.finished after a monitor fix.
        Result is applied to the UI from _on_refresh_result on the main
        thread.
        """
        runtime = self._runtime
        # Guard: refresh during a pipeline run could mutate
        # runtime["preloaded_specs"]["DisplayCapabilities"] while
        # PipelineWorker is still iterating ctx.specs (which aliases the
        # same dict in the snapshot-fallback path from phase_scan). Same
        # shape of bug as CR-1 for on_monitor_fix_requested.
        if runtime.get("pipeline_thread") is not None:
            self._log.warning("Monitor refresh suppressed: pipeline is running")
            return
        if runtime.get("monitor_refresh_thread") is not None:
            return  # already in-flight; the existing worker will deliver the result
        from src.gui.worker import _MonitorRefreshWorker
        refresh_thread = QThread()
        refresh_worker = _MonitorRefreshWorker()
        refresh_worker.moveToThread(refresh_thread)
        refresh_thread.started.connect(refresh_worker.run)
        refresh_worker.finished.connect(self._on_refresh_result)
        refresh_worker.failed.connect(self._on_refresh_failed)
        refresh_worker.finished.connect(refresh_thread.quit)
        refresh_worker.failed.connect(refresh_thread.quit)
        refresh_thread.finished.connect(refresh_worker.deleteLater)
        refresh_thread.finished.connect(refresh_thread.deleteLater)
        refresh_thread.finished.connect(lambda: runtime.pop("monitor_refresh_thread", None))
        refresh_thread.finished.connect(lambda: runtime.pop("monitor_refresh_worker", None))
        runtime["monitor_refresh_thread"] = refresh_thread
        runtime["monitor_refresh_worker"] = refresh_worker
        refresh_thread.start()

    def _on_refresh_result(self, displays: list) -> None:
        main = self._main
        runtime = self._runtime
        main._dashboard.set_monitor_data(displays)
        sp = runtime.get("preloaded_specs", {}) or {}
        sp["DisplayCapabilities"] = displays
        runtime["preloaded_specs"] = sp

    def _on_refresh_failed(self, exc_str: str) -> None:
        self._log.warning("Could not refresh monitor card: %s", exc_str)

    def on_monitor_fix_requested(self, device: str) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
        # Guard: dashboard fix during a pipeline run races ApplyPhase's
        # _fix_display -- concurrent ChangeDisplaySettingsExW + concurrent
        # manifest appends would record the wrong "before" state and break
        # revert.
        if runtime.get("pipeline_thread") is not None:
            log.warning("Monitor fix suppressed: pipeline is running")
            return
        # Guard: rapid double-click would spawn two _MonitorFixWorker threads;
        # the second's manifest "before" entry would be the first's after.
        if runtime.get("monitor_fix_thread") is not None:
            log.warning("Monitor fix already in progress -- ignoring")
            return
        specs = runtime.get("preloaded_specs", {}) or {}
        displays = specs.get("DisplayCapabilities", []) or []
        target = next((d for d in displays if d.get("device") == device), None)
        if target is None:
            log.warning("Monitor fix requested for unknown device: %s", device)
            return
        desc = (
            f"{device}: Current {target.get('current_refresh_hz', '?')}Hz  →  "
            f"Max {target.get('max_refresh_hz', '?')}Hz at {target.get('at_resolution', '')}"
        )
        proposal = {
            "finding": "display",
            "title": "Set Monitor to Maximum Refresh Rate",
            "sev": "medium",
            "desc": desc,
            "can_auto_fix": True,
            "mode": "AUTO",
            "tag": "DISPLAY",
        }
        from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
        dialog = BatchSelectionDialog([proposal], parent=main)
        if not dialog.exec() or not dialog.selected_indices():
            return
        # Filter so _fix_display targets ONLY this device
        filtered_specs = {**specs, "DisplayCapabilities": [target]}
        from src.gui.worker import _MonitorFixWorker
        fix_thread = QThread()
        fix_worker = _MonitorFixWorker(filtered_specs)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(self.refresh_monitor_card)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        runtime["monitor_fix_thread"] = fix_thread
        runtime["monitor_fix_worker"] = fix_worker
        fix_thread.finished.connect(lambda: runtime.pop("monitor_fix_thread", None))
        fix_thread.finished.connect(lambda: runtime.pop("monitor_fix_worker", None))
        fix_thread.start()
