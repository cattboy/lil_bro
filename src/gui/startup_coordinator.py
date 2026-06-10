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


class StartupCoordinator(QObject):
    """Owns the StartupOrchestrator + monitor-refresh-card signal handlers.

    Constructed once by ``app.run()``; the shared ``runtime`` dict is stored
    by reference. ``pipeline`` is the PipelineController -- ``on_finished``
    re-enables the flow controls through it once startup completes.
    """

    def __init__(self, main, runtime: dict, log, orchestrator, pipeline, parent=None) -> None:
        # QObject base anchors this coordinator's slots to the thread it is built
        # on (the main/GUI thread). Without it, the card-fix worker QThreads'
        # cross-thread signals (fix_thread.finished, worker.result) fall back to
        # DirectConnection and run on the dying worker thread -- stranding the
        # card_fix_in_progress cleanup (dashboard locks) and mutating widgets
        # off-thread (parent=None). See StartupCompleter for the same rationale.
        super().__init__(parent)
        self._main = main
        self._runtime = runtime
        self._log = log
        self._orchestrator = orchestrator
        self._pipeline = pipeline
        # NVIDIA card-fix check_name, captured at request time so the queued
        # result slot reads it without a fragile self.sender() lookup on a
        # possibly-deleted worker.
        self._nvidia_fix_check_name: str | None = None
        # Power Plan / Game Mode card-fix check_name -- same capture-at-request
        # rationale as _nvidia_fix_check_name.
        self._setting_fix_check_name: str | None = None
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

    @Slot()
    def refresh_fix_cards_after_revert(self) -> None:
        """Re-scan the Dashboard fix cards after a revert.

        A successful card fix optimistically flips its card to the "applied"
        state (e.g. _on_nvidia_fix_result -> set_nvidia_profile_findings({"status":
        "OK"})) without updating preloaded_specs. A revert restores the original
        settings but nothing re-scanned those cards, so they stayed "applied".

        Wired to RevertWorker.revert_finished from PipelineController.start_revert.
        This coordinator is a QObject on the GUI thread, so the cross-thread
        signal delivers here as a QueuedConnection -- safe to mutate widgets.
        """
        runtime = self._runtime
        # Specs may be mid-mutation during a pipeline run; revert and pipeline are
        # mutually exclusive, so this should not normally fire then, but guard anyway.
        if runtime.get("pipeline_thread") is not None:
            return
        specs = runtime.get("preloaded_specs", {}) or {}
        # NVIDIA: analyze_nvidia_profile is pure over the cached preloaded_specs --
        # the same snapshot startup wiring used and that the apply never updated --
        # so re-running it restores the pre-apply WARNING/OK state on the GUI thread.
        try:
            from src.agent_tools.nvidia_profile import analyze_nvidia_profile
            self._main._dashboard.set_nvidia_profile_findings(analyze_nvidia_profile(specs))
        except Exception as exc:
            self._log.warning("NVIDIA card refresh after revert failed: %s", exc, exc_info=True)
        # Power Plan / Game Mode: same pure-analyzer-over-cached-specs path --
        # the apply never mutated preloaded_specs, so the cached snapshot
        # reflects the pre-fix state these cards should return to.
        try:
            from src.agent_tools.game_mode import analyze_game_mode
            from src.agent_tools.power_plan import analyze_power_plan
            self._main._dashboard.set_power_plan_findings(analyze_power_plan(specs))
            self._main._dashboard.set_game_mode_findings(analyze_game_mode(specs))
        except Exception as exc:
            self._log.warning("Power Plan/Game Mode card refresh after revert failed: %s", exc, exc_info=True)
        # Monitor (display): same staleness gap after a display revert.
        # refresh_monitor_card re-probes capabilities LIVE on its own worker thread
        # and already guards against a running pipeline / an in-flight refresh.
        try:
            self.refresh_monitor_card()
        except Exception as exc:
            self._log.warning("Monitor card refresh after revert failed: %s", exc, exc_info=True)

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

        # Wire the Dashboard Retry button once. on_finished fires exactly once
        # per session, and the button isn't clickable until the dashboard shows
        # (after this), so connecting here is race-free.
        if not runtime.get("_thermal_retry_wired", False):
            try:
                main._dashboard.thermal_retry_requested.connect(self.on_thermal_retry_requested)
                runtime["_thermal_retry_wired"] = True
            except Exception as exc:
                log.warning("Could not wire thermal retry button: %s", exc, exc_info=True)

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

            # Surface the thermal failure cause on the card. The orchestrator
            # records lhm_failure_reason for BOTH a failed start() (startup_lhm
            # is None) AND the running-but-no-sensors PawnIO case (startup_lhm is
            # the live instance) -- so key off the reason, not just None. The
            # Retry button is shown only on failure and stays hidden when thermal
            # monitoring is healthy.
            reason = getattr(self._orchestrator, "lhm_failure_reason", "") or ""
            if reason:
                main._dashboard.thermal_chart.set_offline(reason)
                main._dashboard.set_thermal_retry_visible(True)
            elif startup_lhm is None:
                main._dashboard.thermal_chart.set_offline("Thermal monitor unavailable")
                main._dashboard.set_thermal_retry_visible(True)
            else:
                main._dashboard.set_thermal_retry_visible(False)
        except Exception as exc:
            log.error("on_finished EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

        # Late-fire monitor + NVIDIA card wiring: if main.show() already ran
        # before this slot fired (slow-path on iGPU machines), wire here. The
        # post-splash block in run() wires on the fast-path. _monitor_wired
        # prevents double-wire (both monitor and NVIDIA cards wire together).
        if main.isVisible() and not runtime.get("_monitor_wired", False):
            try:
                _specs = runtime.get("preloaded_specs", {}) or {}
                main._dashboard.set_monitor_data(_specs.get("DisplayCapabilities", []))
                main._dashboard.monitor_fix_requested.connect(self.on_monitor_fix_requested)
                main._dashboard.monitor_refresh_requested.connect(self.refresh_monitor_card)
                main._dashboard.seed_dlss_priority(_specs)
                main._dashboard.set_nvidia_data(_specs.get("NVIDIA", []))
                # Findings parity with the fast path (app.py run()) -- without
                # this, slow-path machines never got the NVIDIA WARNING/OK text.
                from src.agent_tools.nvidia_profile import analyze_nvidia_profile
                main._dashboard.set_nvidia_profile_findings(analyze_nvidia_profile(_specs))
                main._dashboard.nvidia_fix_requested.connect(self.on_nvidia_fix_requested)
                from src.agent_tools.game_mode import analyze_game_mode
                from src.agent_tools.power_plan import analyze_power_plan
                main._dashboard.set_power_plan_data(_specs.get("PowerPlan"))
                main._dashboard.set_game_mode_data(_specs.get("GameMode"))
                main._dashboard.set_power_plan_findings(analyze_power_plan(_specs))
                main._dashboard.set_game_mode_findings(analyze_game_mode(_specs))
                main._dashboard.power_plan_fix_requested.connect(self.on_power_plan_fix_requested)
                main._dashboard.game_mode_fix_requested.connect(self.on_game_mode_fix_requested)
                runtime["_monitor_wired"] = True
                log.info("GUI Startup: monitor + NVIDIA + power/game cards wired (late-fire path)")
            except Exception as exc:
                log.warning("Could not wire monitor/NVIDIA cards (late path): %s", exc, exc_info=True)

        # Seed the Applied Fixes card (T-016). on_finished fires exactly once per
        # session on both the fast and slow startup paths, so seeding here covers
        # both without editing app.run(). The card is pre-allocated in
        # RevertView.__init__; the QFileSystemWatcher keeps it fresh thereafter.
        # Reuses _reload_last_run -- the same load_manifest + set_last_run path.
        self._reload_last_run()

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
        refresh_thread.finished.connect(self._on_refresh_thread_finished)
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
        # manifest appends would record the wrong "before" state and break revert.
        if runtime.get("pipeline_thread") is not None:
            log.warning("Monitor fix suppressed: pipeline is running")
            return
        # Guard: only one card fix at a time. Prevents concurrent NPI imports,
        # double restore-point creation, and manifest-write races.
        if runtime.get("card_fix_in_progress"):
            log.warning("Monitor fix suppressed: a card fix is already in progress")
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
        # Restore-point gate (shared across all dashboard card fixes). Approval
        # collected here on the GUI thread; the worker creates it non-interactively.
        create_rp = self._ensure_restore_point_choice(main)
        # Filter so _fix_display targets ONLY this device
        filtered_specs = {**specs, "DisplayCapabilities": [target]}
        from src.gui.worker import _MonitorFixWorker
        fix_thread = QThread()
        fix_worker = _MonitorFixWorker(filtered_specs, create_rp)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(self.refresh_monitor_card)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        fix_worker.result.connect(self._on_monitor_fix_result)
        runtime["monitor_fix_thread"] = fix_thread
        runtime["monitor_fix_worker"] = fix_worker
        runtime["card_fix_in_progress"] = True
        if create_rp:
            runtime["restore_point_in_progress"] = True
        fix_thread.finished.connect(self._on_monitor_fix_thread_finished)
        fix_thread.start()


    def _ensure_restore_point_choice(self, parent) -> bool:
        """GUI-thread gate: decide whether the worker should create a restore point.

        Returns True only when no restore point exists yet this session (per the
        session manifest) AND the user accepts the prompt. The actual creation
        runs non-interactively in the fix worker via
        ``create_restore_point(assume_approved=True)`` -- collecting approval
        here (not in the worker) avoids the ``prompt_approval`` deadlock in the
        event-loop-less worker thread. The pipeline's BootstrapPhase consults the
        same manifest flag, so a card-created restore point isn't asked for twice.
        """
        from src.utils.revert import load_manifest
        manifest = load_manifest()
        if manifest is not None and manifest.get("restore_point_created"):
            return False  # already created this session; pipeline + cards reuse it
        from src.gui.widgets.confirm_dialog import ConfirmDialog
        dlg = ConfirmDialog(
            "Create a System Restore Point?",
            "Recommended before changing system settings — it lets you roll back if "
            "anything goes wrong. Created once per session (this may take a minute).",
            parent=parent,
            yes_label="Create Restore Point",
            no_label="Skip",
        )
        return bool(dlg.exec())

    def _on_card_fix_result(self, check_name: str, ok: bool) -> None:
        """Show an error dialog if a dashboard card fix failed."""
        if not ok:
            from src.gui.widgets.dialogs import CardDialog
            CardDialog(
                "Fix failed",
                f"The {check_name} fix did not complete. Check the debug log for details.",
                tone="error",
                parent=self._main,
            ).exec()

    # ── Card-fix worker-thread cleanup (queued to the GUI thread) ───────
    # These run as their OWN queued events on the main thread (this coordinator
    # is a QObject). Each clears card_fix_in_progress FIRST/unconditionally so a
    # later exception in any sibling slot on the same QThread.finished signal
    # (e.g. refresh_monitor_card) can never strand the guard and lock the
    # dashboard. Replacing bare-lambda connections also fixes the off-main-thread
    # set_monitor_data / leaked refresh QThread that prevented a clean exit.

    @Slot()
    def _on_monitor_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("monitor_fix_thread", None)
        runtime.pop("monitor_fix_worker", None)

    @Slot()
    def _on_nvidia_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("nvidia_fix_thread", None)
        runtime.pop("nvidia_fix_worker", None)

    @Slot()
    def _on_setting_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("setting_fix_thread", None)
        runtime.pop("setting_fix_worker", None)

    @Slot()
    def _on_refresh_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("monitor_refresh_thread", None)
        runtime.pop("monitor_refresh_worker", None)

    @Slot()
    def _on_thermal_retry_thread_finished(self) -> None:
        # Pops only thermal_retry_thread; _on_thermal_retry_finished owns the
        # thermal_retry_worker pop (it reads the worker's result first).
        self._runtime.pop("thermal_retry_thread", None)

    @Slot(bool)
    def _on_monitor_fix_result(self, ok: bool) -> None:
        """Queued (main-thread) wrapper for the monitor card-fix result."""
        self._on_card_fix_result("display", ok)

    @Slot(bool)
    def _on_nvidia_fix_result(self, ok: bool) -> None:
        """Queued (main-thread) wrapper for the NVIDIA card-fix result.

        Reads the check_name captured in on_nvidia_fix_requested rather than
        self.sender() -- the latter is unreliable for queued connections and
        risks dereferencing a deleteLater-d worker.
        """
        check_name = self._nvidia_fix_check_name or "nvidia_profile"
        self._on_card_fix_result(check_name, ok)
        if ok and check_name == "nvidia_profile":
            self._main._dashboard.set_nvidia_profile_findings({"status": "OK"})

    @Slot(bool)
    def _on_setting_fix_result(self, ok: bool) -> None:
        """Queued (main-thread) wrapper for the Power Plan / Game Mode result.

        Reads the check_name captured in _start_setting_fix rather than
        self.sender() -- the latter is unreliable for queued connections and
        risks dereferencing a deleteLater-d worker.
        """
        check_name = self._setting_fix_check_name or "power_plan"
        self._on_card_fix_result(check_name, ok)
        if ok:
            # Optimistic applied state; a revert re-scans via
            # refresh_fix_cards_after_revert.
            if check_name == "game_mode":
                self._main._dashboard.set_game_mode_findings({"status": "OK"})
            else:
                self._main._dashboard.set_power_plan_findings({"status": "OK"})

    def on_nvidia_fix_requested(self, check_name: str) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
        # Guard: a dashboard NVIDIA fix during a pipeline run races ApplyPhase's
        # nvidia_profile fix -- concurrent NPI imports + manifest appends.
        if runtime.get("pipeline_thread") is not None:
            log.warning("NVIDIA fix suppressed: pipeline is running")
            return
        # Guard: only one card fix at a time. Prevents concurrent NPI imports,
        # double restore-point creation, and manifest-write races.
        if runtime.get("card_fix_in_progress"):
            log.warning("NVIDIA fix suppressed: a card fix is already in progress")
            return
        specs = runtime.get("preloaded_specs", {}) or {}
        nvidia = specs.get("NVIDIA", [])
        if not isinstance(nvidia, list) or not nvidia:
            log.warning("NVIDIA fix requested but no NVIDIA GPU in specs")
            return

        gpu_name = str(nvidia[0].get("GPU") or "your NVIDIA GPU")
        if check_name == "nvidia_dlss_preset":
            from src.utils.dlss_presets import get_preset
            preset = get_preset(gpu_name)
            letter = preset.letter if preset is not None else "?"
            title = f"Set DLSS Preset {letter}"
            desc = (
                f"{gpu_name}: force DLSS Preset {letter} (the recommended AI upscaling "
                f"model for your GPU). Changes ONLY the DLSS preset — "
                f"All changes revertable and backed up, lil_bro has your back"
            )
            tag = "NVIDIA DLSS"
        else:  # nvidia_profile (full)
            title = "Optimize NVIDIA Driver Profile"
            desc = (
                f"{gpu_name}: apply the Nvidia Profile Inspector gaming profile (MORE FPS) — "
                f"enables G-Sync, VSync, FPS cap, ReBar, "
                f"and Maximum Performance power mode. All changes revertable and backed up "
                f"with lil_bro looking out"
            )
            tag = "NVIDIA"

        proposal = {
            "finding": check_name,
            "title": title,
            "sev": "medium",
            "desc": desc,
            "can_auto_fix": True,
            "mode": "AUTO",
            "tag": tag,
        }
        from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
        dialog = BatchSelectionDialog([proposal], parent=main)
        if not dialog.exec() or not dialog.selected_indices():
            return

        # Restore-point gate (shared with the monitor fix). Approval collected
        # here on the GUI thread; the worker creates it non-interactively.
        create_rp = self._ensure_restore_point_choice(main)

        # Filter so the handler only sees the NVIDIA payload.
        filtered_specs = {**specs, "NVIDIA": nvidia}
        self._nvidia_fix_check_name = check_name
        from src.gui.worker import _CardFixWorker
        fix_thread = QThread()
        fix_worker = _CardFixWorker(check_name, filtered_specs, create_rp)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        fix_worker.result.connect(self._on_nvidia_fix_result)
        runtime["nvidia_fix_thread"] = fix_thread
        runtime["nvidia_fix_worker"] = fix_worker
        runtime["card_fix_in_progress"] = True
        if create_rp:
            runtime["restore_point_in_progress"] = True
        fix_thread.finished.connect(self._on_nvidia_fix_thread_finished)
        fix_thread.start()

    # ── Power Plan / Game Mode card fixes (T-034) ───────────────────────
    # One card per fix (the dashboard is the pick-and-choose path; the
    # pipeline is apply-all); both route through the shared
    # _start_setting_fix below.

    def on_power_plan_fix_requested(self) -> None:
        self._start_setting_fix("power_plan", "PowerPlan", "POWER PLAN")

    def on_game_mode_fix_requested(self) -> None:
        self._start_setting_fix("game_mode", "GameMode", "GAME MODE")

    def _start_setting_fix(self, check_name: str, spec_key: str, tag: str) -> None:
        """Shared approval + worker spawn for the Power Plan / Game Mode cards.

        Mirrors on_nvidia_fix_requested: guards -> BatchSelectionDialog ->
        restore-point gate -> _CardFixWorker on its own QThread. ``check_name``
        must exactly match the @register_fix key in fix_dispatch.py.
        """
        runtime = self._runtime
        main = self._main
        log = self._log
        # Guard: a dashboard fix during a pipeline run races ApplyPhase's
        # handler for the same check -- concurrent system writes + manifest
        # appends.
        if runtime.get("pipeline_thread") is not None:
            log.warning("%s fix suppressed: pipeline is running", check_name)
            return
        # Guard: only one card fix at a time. Prevents double restore-point
        # creation and manifest-write races.
        if runtime.get("card_fix_in_progress"):
            log.warning("%s fix suppressed: a card fix is already in progress", check_name)
            return
        specs = runtime.get("preloaded_specs", {}) or {}
        entry = specs.get(spec_key)
        # Same gate as Dashboard.set_*_data: no before-state means the fix
        # would record as non-revertible -- never offer that path.
        if not isinstance(entry, dict) or not entry or "error" in entry:
            log.warning("%s fix requested but no usable %s entry in specs", check_name, spec_key)
            return

        # Canonical title/explanation from FALLBACK_PROPOSALS -- single source
        # of truth shared with the pipeline approval flow (no hardcoded copy).
        from src.llm.action_proposer import propose_for_check
        prop = propose_for_check(check_name) or {}
        sev = {"HIGH": "high", "MEDIUM": "medium"}.get(str(prop.get("severity", "")), "medium")
        proposal = {
            "finding": check_name,
            "title": str(prop.get("proposed_action", check_name)),
            "sev": sev,
            "desc": (
                f"{prop.get('explanation', '')} "
                f"All changes revertable and backed up, lil_bro has your back"
            ),
            "can_auto_fix": True,
            "mode": "AUTO",
            "tag": tag,
        }
        from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
        dialog = BatchSelectionDialog([proposal], parent=main)
        if not dialog.exec() or not dialog.selected_indices():
            return

        # Restore-point gate (shared with the monitor/NVIDIA fixes). Approval
        # collected here on the GUI thread; the worker creates it
        # non-interactively.
        create_rp = self._ensure_restore_point_choice(main)

        # Strictly narrowed: _fix_power_plan/_fix_game_mode read only their
        # own spec key.
        filtered_specs = {spec_key: dict(entry)}
        self._setting_fix_check_name = check_name
        from src.gui.worker import _CardFixWorker
        fix_thread = QThread()
        fix_worker = _CardFixWorker(check_name, filtered_specs, create_rp)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        fix_worker.result.connect(self._on_setting_fix_result)
        runtime["setting_fix_thread"] = fix_thread
        runtime["setting_fix_worker"] = fix_worker
        runtime["card_fix_in_progress"] = True
        if create_rp:
            runtime["restore_point_in_progress"] = True
        fix_thread.finished.connect(self._on_setting_fix_thread_finished)
        fix_thread.start()


    def on_thermal_retry_requested(self) -> None:
        """Relaunch the thermal sidecar off the GUI thread (Dashboard Retry button).

        Mirrors on_monitor_fix_requested's QThread + worker wiring, but the worker
        calls ``sidecar.start()`` directly -- NOT ``execute_fix`` (a relaunch is not
        a revertible fix). Guards against concurrent retries and disables the button
        while one is in flight.
        """
        runtime = self._runtime
        main = self._main
        log = self._log
        if runtime.get("thermal_retry_thread") is not None:
            log.warning("Thermal retry already in progress -- ignoring")
            return
        main._dashboard.set_thermal_retry_enabled(False)
        main._dashboard.thermal_chart.set_offline("Retrying thermal monitor…")
        from src.gui.worker import _ThermalRetryWorker
        thread = QThread()
        worker = _ThermalRetryWorker(runtime.get("lhm"))
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(thread.quit)
        # _on_thermal_retry_finished is connected FIRST so it reads the worker's
        # result before deleteLater schedules its teardown.
        thread.finished.connect(self._on_thermal_retry_finished)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        runtime["thermal_retry_thread"] = thread
        runtime["thermal_retry_worker"] = worker
        thread.finished.connect(self._on_thermal_retry_thread_finished)
        thread.start()

    def _on_thermal_retry_finished(self) -> None:
        """Main-thread handler: apply the retry result, re-enable the button.

        Reads the worker's result attributes before its runtime ref is popped. On
        success, ``start_polling()`` is idempotent and the chart self-heals when the
        next snapshot arrives (``append_sample`` clears the offline overlay) and the
        Retry button hides; on failure the classified cause is shown on the card and
        the button stays visible so the user can try again.
        """
        runtime = self._runtime
        main = self._main
        worker = runtime.get("thermal_retry_worker")
        try:
            if worker is not None:
                if worker.new_lhm is not None:
                    runtime["lhm"] = worker.new_lhm
                if worker.available:
                    main._dashboard.start_polling()
                    main._dashboard.set_thermal_retry_visible(False)
                else:
                    main._dashboard.thermal_chart.set_offline(
                        worker.reason or "Thermal monitor unavailable"
                    )
                    main._dashboard.set_thermal_retry_visible(True)
        except Exception as exc:
            self._log.error("thermal retry finish EXC: %r", exc, exc_info=True)
        finally:
            runtime.pop("thermal_retry_worker", None)
            try:
                main._dashboard.set_thermal_retry_enabled(True)
            except Exception:
                pass  # safe: button re-enable is best-effort
