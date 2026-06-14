"""Pipeline + revert orchestration controller for the GUI.

Extracted from ``app.run()``'s closure: owns the optimization-pipeline run,
the revert run, the approval / confirm / batch dialogs, and the live output /
progress / benchmark signal handlers. ``app.run()`` constructs one instance
and connects the bridge + nav-button signals to its methods.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread

from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
from src.gui.widgets.confirm_dialog import ConfirmDialog
from src.gui.worker import PipelineWorker, RevertWorker


class PipelineController:
    """Owns the pipeline/revert lifecycle and the dialog + output handlers.

    Constructed once by ``app.run()``; the shared ``runtime`` dict is stored
    by reference (never copied) so the run() spine and StartupCoordinator
    observe the same pipeline/revert thread state.
    """

    def __init__(self, main, bridge, runtime: dict, log, ansi_re) -> None:
        self._main = main
        self._bridge = bridge
        self._runtime = runtime
        self._log = log
        self._ansi_re = ansi_re

    # ── Flow controls ──────────────────────────────────────────────────

    def set_flow_controls(self, enabled: bool) -> None:
        if not enabled and not self._runtime.get("startup_done", False):
            return
        self._main._run_button.setEnabled(enabled)
        self._main._revert_button.setEnabled(enabled)
        self._main._ai_setup_button.setEnabled(enabled)
        self._main._revert_view.set_revert_enabled(enabled)

    # ── Approval / confirm / batch dialogs ─────────────────────────────

    def show_approval_dialog(self, action_text: str) -> None:
        # Approval prompts reuse the shared ConfirmDialog (same card + glowing
        # W button as every other dialog); the action text becomes the body.
        dialog = ConfirmDialog(
            "Requires Approval",
            action_text,
            parent=self._main,
            yes_label="Approve",
            no_label="Deny",
        )
        approved = bool(dialog.exec())
        self._bridge.deliver_answer(approved)

    def show_confirm_dialog(self, title: str, description: str) -> None:
        dialog = ConfirmDialog(title, description, parent=self._main)
        confirmed = bool(dialog.exec())
        self._bridge.deliver_answer(confirmed)

    def show_batch_dialog(self, proposals: list) -> None:
        dialog = BatchSelectionDialog(proposals, parent=self._main)
        dialog.exec()
        indices = dialog.selected_indices()
        self._log.info("show_batch_dialog: delivered indices=%s", indices)
        self._bridge.deliver_answer(indices)

    def show_mouse_ready_dialog(self) -> None:
        from src.gui.widgets.mouse_ready_dialog import MouseReadyDialog
        dialog = MouseReadyDialog(parent=self._main)
        dialog.exec()
        self._bridge.deliver_answer(True)

    def on_mouse_poll_result(self, result: object) -> None:
        try:
            self._main._dashboard.receive_poll_result(result)
        except Exception as e:
            self._log.debug("mouse poll result notify failed: %s", e)

    # ── Live output / progress / benchmark ─────────────────────────────

    def on_pipeline_output(self, text: str) -> None:
        for raw in text.splitlines():
            line = self._ansi_re.sub("", raw).strip()
            if line:
                self._main.status_bar_widget.set_state("run", line[:80])
            try:
                self._main._output_panel.append_line(raw)
            except Exception as e:
                self._log.debug("output panel append failed: %s", e)

    def on_progress_changed(self, percent: int, label: str) -> None:
        self._main._progress_bar.setValue(percent)
        self._main._progress_label.setText(label)
        if not self._main._progress_bar.isVisible():
            self._main._progress_bar.setVisible(True)
            self._main._progress_label.setVisible(True)

    def on_benchmark_score(self, phase: str, scores: object, cpu_peak: object) -> None:
        try:
            self._main.update_benchmark_score(
                phase,
                scores if isinstance(scores, dict) else {},
                cpu_peak if isinstance(cpu_peak, (int, float)) else None,
            )
        except Exception as e:
            self._log.debug("benchmark score notify failed: %s", e)

    def on_benchmark_started(self) -> None:
        try:
            self._main._benchmark_row.set_benchmark_started()
        except Exception:
            pass  # safe: benchmark_row may not exist yet on early signal arrival

    # ── Pipeline run ───────────────────────────────────────────────────

    def confirm_start_pipeline(self) -> None:
        """Prompt before starting the pipeline.

        Wired to the sidebar Run button. The button's own
        ``show_output()`` connection has already navigated to the output
        view, so the modal prompt appears over it. Only an explicit
        confirm starts the run; declining leaves the user idle on the
        output page. Guards mirror ``start_pipeline`` so we never prompt
        while a run is in flight or before startup has finished.
        """
        runtime = self._runtime
        main = self._main
        if runtime.get("pipeline_thread") is not None:
            return
        if runtime.get("lhm") is None:
            main.status_bar_widget.set_state(
                "ok", "Startup still in progress — please wait…"
            )
            return
        dialog = ConfirmDialog(
            "Start Optimization?",
            "lil_bro will analyze your system and propose fixes. Nothing "
            "changes without your approval at each step.",
            parent=main,
            yes_label="Start Optimization",
            no_label="Not Yet",
        )
        if dialog.exec():
            self.start_pipeline()

    def start_pipeline(self) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
        if runtime.get("pipeline_thread") is not None:
            return
        if runtime.get("lhm") is None:
            main.status_bar_widget.set_state("ok", "Startup still in progress — please wait…")
            return
        log.info("Pipeline: start requested")
        self.set_flow_controls(False)
        main.show_output()
        main.set_running(True)
        main._benchmark_row.reset()
        main.status_bar_widget.set_state("run", "Pipeline starting…")

        # Snapshot the session manifest's fix count BEFORE the run. The delta
        # after the run is exactly this run's applied fixes (card fixes are
        # guarded off while the pipeline runs), which scopes the post-run
        # dashboard re-collect to only the cards that changed.
        from src.utils.revert import load_manifest
        runtime["_pipeline_manifest_fix_count"] = len((load_manifest() or {}).get("fixes", []))

        pipeline_thread = QThread()
        pipeline_worker = PipelineWorker(lhm=runtime["lhm"], llm=None, preloaded_specs=runtime.get("preloaded_specs", {}))
        pipeline_worker.moveToThread(pipeline_thread)
        pipeline_thread.started.connect(pipeline_worker.run)

        def _on_pipeline_started() -> None:
            log.info("Pipeline: started")
            main.status_bar_widget.set_state("run", "Pipeline running…")
            main._benchmark_row.set_pipeline_running()

        def _on_pipeline_finished() -> None:
            log.info("Pipeline: finished (PASS)")
            main.status_bar_widget.set_state("ok", "Pipeline finished")
            main._benchmark_row.set_pipeline_complete()
            pipeline_thread.quit()

        def _on_pipeline_failed(exc_type: str, msg: str, tb: str) -> None:
            log.error("Pipeline: failed -- %s: %s\n%s", exc_type, msg, tb)
            main.status_bar_widget.set_state("ok", f"Pipeline failed: {exc_type}")
            main._benchmark_row.set_pipeline_failed()
            pipeline_thread.quit()

        def _on_thread_done() -> None:
            self.set_flow_controls(True)
            main.set_running(False)
            runtime["pipeline_thread"] = None
            runtime["pipeline_worker"] = None
            main._progress_bar.setVisible(False)
            main._progress_label.setVisible(False)
            try:
                main.stop_requested.disconnect(pipeline_worker.request_cancel)
            except (RuntimeError, TypeError):
                # Disconnect raises if the connection was already broken
                # (e.g. worker was deleted). Safe to ignore on teardown.
                pass
            pipeline_worker.deleteLater()
            pipeline_thread.deleteLater()
            # Dashboard fix cards were built from the pre-run spec snapshot; the
            # run may have applied fixes, leaving the cards showing stale data /
            # offering already-applied fixes. Scope the live re-collect to just
            # the sections this run's fixes touched (manifest delta) and skip it
            # entirely when nothing was applied. Runs after pipeline_thread is
            # cleared above so refresh_dashboard_fix_cards' guard passes.
            startup = runtime.get("_startup_coordinator")
            if startup is not None:
                from src.gui.startup_coordinator import _sections_for_fixes
                from src.utils.revert import load_manifest
                before = runtime.pop("_pipeline_manifest_fix_count", 0)
                new_fixes = (load_manifest() or {}).get("fixes", [])[before:]
                scope = _sections_for_fixes(e.get("fix", "") for e in new_fixes)
                startup.refresh_dashboard_fix_cards(scope)

        pipeline_worker.pipeline_started.connect(_on_pipeline_started)
        pipeline_worker.pipeline_finished.connect(_on_pipeline_finished)
        pipeline_worker.pipeline_failed.connect(_on_pipeline_failed)
        pipeline_thread.finished.connect(_on_thread_done)
        # Cancel signal from MainWindow Stop button / Esc / Q / Enter hotkeys.
        # MUST be DirectConnection -- the worker thread's event loop is
        # blocked inside the synchronous run_optimization_pipeline call,
        # so a QueuedConnection slot would sit in the queue until run()
        # returned (which is what we're trying to cancel: deadlock).
        # DirectConnection runs request_cancel on the GUI thread, calling
        # _cancel_event.set() from there. The worker's polling loop reads
        # the Event on its next iteration. Same mechanism the existing
        # closeEvent path uses (direct call, no signal).
        main.stop_requested.connect(
            pipeline_worker.request_cancel,
            Qt.ConnectionType.DirectConnection,
        )

        runtime["pipeline_thread"] = pipeline_thread
        runtime["pipeline_worker"] = pipeline_worker
        pipeline_thread.start()

    # ── Revert run ─────────────────────────────────────────────────────

    def start_revert(self) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
        if runtime.get("revert_thread") is not None:
            return
        from src.utils.revert import load_manifest
        manifest = load_manifest()
        if manifest is None:
            main.status_bar_widget.set_state("ok", "No session backup found — nothing to revert")
            return

        # Capture which sections the to-be-reverted fixes touch BEFORE the worker
        # runs -- a successful revert deletes the manifest, so refresh_fix_cards_
        # after_revert can no longer read it. This scopes the post-revert live
        # re-collect to just the affected cards.
        from src.gui.startup_coordinator import _sections_for_fixes
        runtime["_revert_refresh_scope"] = _sections_for_fixes(
            e.get("fix", "") for e in manifest.get("fixes", [])
        )

        self.set_flow_controls(False)
        main.status_bar_widget.set_state("run", "Reverting session…")

        revert_thread = QThread()
        revert_worker = RevertWorker()
        revert_worker.moveToThread(revert_thread)
        revert_thread.started.connect(revert_worker.run)

        def _on_revert_finished() -> None:
            main.status_bar_widget.set_state("ok", "Revert complete")
            revert_thread.quit()

        def _on_revert_failed(exc_type: str, msg: str, tb: str) -> None:
            log.error("Revert: GUI revert failed -- %s: %s\n%s", exc_type, msg, tb)
            main.status_bar_widget.set_state("ok", f"Revert failed: {exc_type}")
            revert_thread.quit()

        def _on_revert_thread_done() -> None:
            self.set_flow_controls(True)
            runtime["revert_thread"] = None
            runtime["revert_worker"] = None
            revert_worker.deleteLater()
            revert_thread.deleteLater()

        revert_worker.revert_finished.connect(_on_revert_finished)
        revert_worker.revert_failed.connect(_on_revert_failed)
        revert_thread.finished.connect(_on_revert_thread_done)

        # Re-scan the Dashboard fix cards once the revert succeeds, so the NVIDIA /
        # monitor cards drop the optimistic "applied" state set at apply time. Routed
        # through StartupCoordinator (a QObject on the GUI thread) -- the local
        # closures above are plain callables that run on the worker thread, so they
        # must not touch dashboard widgets. QObject receiver => QueuedConnection.
        startup = runtime.get("_startup_coordinator")
        if startup is not None:
            revert_worker.revert_finished.connect(startup.refresh_fix_cards_after_revert)

        runtime["revert_thread"] = revert_thread
        runtime["revert_worker"] = revert_worker
        revert_thread.start()

    # ── AI setup ───────────────────────────────────────────────────────

    def open_ai_setup(self) -> None:
        from src.gui.widgets.ai_setup_dialog import AISetupDialog
        dialog = AISetupDialog(parent=self._main)
        dialog.exec()

    # ── System Restore ─────────────────────────────────────────────────

    def open_system_restore(self) -> None:
        """Launch Windows System Restore (rstrui.exe) behind a confirm dialog.

        The dialog copy adapts to whether lil_bro created a restore point this
        session: it names the exact 'lil_bro Pre-Tuning <date>' point when one
        exists, otherwise tells the user to pick any point from before lil_bro
        ran. ``trigger_system_restore`` is a non-blocking ``Popen``, so this
        runs on the GUI thread with no worker (unlike ``start_revert``). See
        ``src.utils.revert.trigger_system_restore``.
        """
        from PySide6.QtWidgets import QDialog

        from src.gui.widgets.dialogs import CardDialog
        from src.utils.revert import load_manifest, trigger_system_restore

        manifest = load_manifest()
        restore_point_created = bool(
            isinstance(manifest, dict) and manifest.get("restore_point_created")
        )
        session_date = ""
        if isinstance(manifest, dict):
            session_date = str(manifest.get("session_date", ""))[:10]

        if restore_point_created:
            label = f"lil_bro Pre-Tuning {session_date}".strip()
            description = (
                "This opens Windows System Restore and rolls your entire PC back "
                "to the snapshot lil_bro saved before tuning — undoing everything "
                "since then, not just lil_bro's changes. Your PC will restart.\n\n"
                f'In the wizard, pick the point named "{label}", then follow the prompts.'
            )
        else:
            description = (
                "This opens Windows System Restore and rolls your entire PC back "
                "to an earlier snapshot — undoing everything since then, not just "
                "lil_bro's changes. Your PC will restart.\n\n"
                "lil_bro didn't create a restore point this session, so pick any "
                "point dated before you ran lil_bro, then follow the prompts."
            )

        confirm = CardDialog(
            "Open System Restore?",
            description,
            tone="warning",
            primary_label="Open System Restore",
            secondary_label="Cancel",
            parent=self._main,
        )
        if confirm.exec() != QDialog.DialogCode.Accepted:
            return

        if not trigger_system_restore(session_date):
            CardDialog(
                "Couldn't open System Restore",
                'lil_bro couldn\'t launch System Restore automatically. Open it '
                'manually: press Start, type "Create a restore point", open it, '
                'then click "System Restore…".',
                tone="error",
                primary_label="OK",
                parent=self._main,
            ).exec()
