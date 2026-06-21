"""Startup orchestration coordinator for the GUI.

Extracted from ``app.run()``'s closure: owns the StartupOrchestrator
step / lhm-ready / finished handlers and the monitor-refresh-card
handlers. ``app.run()`` constructs one instance and routes the
orchestrator + dashboard signals to its methods.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Slot

# Re-exported so existing imports (tests + pipeline_controller) keep resolving
# against this module after the map moved to a leaf module.
from src.gui._startup_sections import (  # noqa: F401
    _FIX_TO_SECTIONS,
    _sections_for_fixes,
)
from src.gui._startup_manifest_watcher import ManifestWatcherMixin
from src.gui._startup_wiring import StartupWiringMixin
from src.gui._startup_dashboard_refresh import DashboardRefreshMixin


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


class StartupCoordinator(
    DashboardRefreshMixin,
    StartupWiringMixin,
    ManifestWatcherMixin,
    QObject,
):
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
        # Monitor card-fix device, captured at request time (same rationale as above).
        self._monitor_fix_device: str | None = None
        # Applied Fixes card (T-016): a QFileSystemWatcher refreshes it live; a
        # single-shot QTimer debounces the double directoryChanged per write.
        self._last_run_watcher = None
        self._last_run_debounce = None
        self._last_manifest_sig = None
        self._init_last_run_watcher()

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
        # In-flight feedback: lock this monitor's Fix button + light the status
        # bar. Store the device so the finished slot can route the reset back to
        # the same card (multi-monitor).
        self._monitor_fix_device = device
        main._dashboard.set_fix_card_applying("display", True, device)
        main.status_bar_widget.set_state("run", "Applying display fix…")
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
        # Reset the busy cue on the monitor card that was fixed (routed by the
        # device stored at request time) + the status bar. refresh_monitor_card
        # (connected earlier on thread.finished) has already re-evaluated the
        # button's visibility; re-enabling a hidden button is harmless.
        try:
            self._main._dashboard.set_fix_card_applying(
                "display", False, self._monitor_fix_device
            )
            self._main.status_bar_widget.set_state("ok", "Idle")
        except Exception:
            pass

    @Slot()
    def _on_nvidia_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("nvidia_fix_thread", None)
        runtime.pop("nvidia_fix_worker", None)
        # Reset the busy cue (button + status bar) for BOTH success and failure
        # -- thread.finished fires either way. Route via the stored check_name
        # (sender() is unreliable for queued connections). Best-effort so a UI
        # reset failure can't strand the guard pops above.
        try:
            self._main._dashboard.set_fix_card_applying(
                self._nvidia_fix_check_name or "nvidia_profile", False
            )
            self._main.status_bar_widget.set_state("ok", "Idle")
        except Exception:
            pass

    @Slot()
    def _on_setting_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("setting_fix_thread", None)
        runtime.pop("setting_fix_worker", None)
        # Reset the busy cue (button + status bar) for both success and failure.
        try:
            self._main._dashboard.set_fix_card_applying(
                self._setting_fix_check_name or "power_plan", False
            )
            self._main.status_bar_widget.set_state("ok", "Idle")
        except Exception:
            pass

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
        # In-flight feedback: lock the card's button + light the status bar
        # before the worker blocks on the NPI export/import (3-10s).
        main._dashboard.set_fix_card_applying(check_name, True)
        main.status_bar_widget.set_state("run", f"Applying {tag} fix…")
        fix_thread.start()

    # ── Power Plan / Game Mode card fixes (T-034) ───────────────────────
    # One card per fix (the dashboard is the pick-and-choose path; the
    # pipeline is apply-all); both route through the shared
    # _start_setting_fix below.

    def on_power_plan_fix_requested(self) -> None:
        self._start_setting_fix("power_plan", "PowerPlan", "POWER PLAN")

    def on_game_mode_fix_requested(self) -> None:
        self._start_setting_fix("game_mode", "GameMode", "GAME MODE")

    def on_hags_fix_requested(self) -> None:
        self._start_setting_fix("hags", "HAGS", "HAGS")

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
        # In-flight feedback: lock the card's button + light the status bar.
        main._dashboard.set_fix_card_applying(check_name, True)
        main.status_bar_widget.set_state("run", f"Applying {tag} fix…")
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
