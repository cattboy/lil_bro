"""Power Plan / Game Mode / HAGS + thermal-retry card fixes (T-034).

Extracted from ``StartupCoordinator`` as a mixin folded into the coordinator
(a ``QObject``) so the worker QThreads' cross-thread slots anchor to the GUI
thread. The Power Plan / Game Mode / HAGS cards share ``_start_setting_fix``;
the thermal Retry button relaunches the sidecar (NOT a revertible fix). Shared
helpers ``_ensure_restore_point_choice`` / ``_on_card_fix_result`` stay on the
core coordinator and resolve via the composed MRO. No ``__init__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Slot


class SettingThermalFixMixin:
    """Power Plan / Game Mode / HAGS card fixes + thermal sidecar retry."""

    if TYPE_CHECKING:
        # Provided by StartupCoordinator.__init__ (mixin; type-checker only).
        _main: Any
        _runtime: dict
        _log: Any
        _setting_fix_check_name: Any

        # Shared helpers on the core coordinator, resolved via the composed MRO.
        def _ensure_restore_point_choice(self, parent) -> bool: ...
        def _on_card_fix_result(self, check_name: str, ok: bool) -> None: ...

    # ── Power Plan / Game Mode / HAGS card fixes (T-034) ─────────────────
    # One card per fix (the dashboard is the pick-and-choose path; the
    # pipeline is apply-all); all route through the shared _start_setting_fix.

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

    @Slot()
    def _on_thermal_retry_thread_finished(self) -> None:
        # Pops only thermal_retry_thread; _on_thermal_retry_finished owns the
        # thermal_retry_worker pop (it reads the worker's result first).
        self._runtime.pop("thermal_retry_thread", None)
