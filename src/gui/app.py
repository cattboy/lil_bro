"""GUI entry point — QApplication + theme + splash + main window orchestration.

Called from ``src/main.py`` when ``--terminal`` is *not* set. Owns the
application object lifecycle, wires the splash → startup orchestrator →
main window handoff, and dismisses both PyInstaller native splash and
the QSplashScreen once startup completes.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from src.gui import theme
from src.gui.startup import StartupOrchestrator
from src.gui.widgets.splash import make_splash, show_splash_error, update_splash
from src.gui.windows.main_window import MainWindow


import traceback

from PySide6.QtCore import Qt

from src.gui.bridge import GuiBridge
from src.gui.signals import PipelineSignals


def run(debug: bool = False) -> int:
    """Boot the GUI. Returns the QApplication exit code."""
    import logging
    import secrets
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger

    level = logging.DEBUG if debug else logging.INFO
    enable_debug_logging(level=level)
    log = get_debug_logger()

    def _install_exception_hooks() -> None:
        def _main_excepthook(exc_type, exc_value, exc_tb):
            log.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))

        def _thread_excepthook(args):
            log.error(
                "Uncaught exception in thread %s",
                args.thread.name if args.thread else "unknown",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        sys.excepthook = _main_excepthook
        threading.excepthook = _thread_excepthook

    _install_exception_hooks()

    import re

    from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
    from src.gui.widgets.approval_dialog import ApprovalDialog
    from src.gui.widgets.confirm_dialog import ConfirmDialog
    from src.gui.worker import PipelineWorker, RevertWorker
    from src.utils.pawnio_check import is_pawnio_installed

    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    log.debug("GUI Startup: app.run() entry")

    try:
        pawnio_was_preinstalled = is_pawnio_installed()
    except Exception:
        pawnio_was_preinstalled = False

    QApplication.setApplicationName("lil_bro")
    QApplication.setOrganizationName("lil_bro")
    app = QApplication.instance() or QApplication(sys.argv)

    theme.load_fonts()
    app.setStyleSheet(theme.build_stylesheet())

    from src.gui.settings import Settings
    settings = Settings()
    main = MainWindow(settings=settings)

    # ── Session identity ───────────────────────────────────────────────
    session_id = secrets.token_hex(4)
    main.status_bar_widget.set_session(session_id)

    # Try to pull model name from LLM config
    try:
        from src.utils.llm_setup import get_model_display_name
        main.status_bar_widget.set_model(get_model_display_name())
    except Exception:
        main.status_bar_widget.set_model("Qwen2.5-7B")

    # ── Splash dialog ──────────────────────────────────────────────────
    from src.gui.widgets.splash import SplashDialog
    splash = SplashDialog(parent=main)

    bridge = GuiBridge(PipelineSignals(), parent=app)
    bridge.install()

    thread = QThread()
    orchestrator = StartupOrchestrator()
    orchestrator.moveToThread(thread)
    thread.started.connect(orchestrator.run)
    orchestrator.finished.connect(thread.quit)

    runtime: dict[str, object] = {
        "lhm": None,
        "bridge": bridge,
        "pipeline_thread": None,
        "pipeline_worker": None,
        "revert_thread": None,
        "revert_worker": None,
    }

    # Wire init_step to splash steps
    orchestrator.init_step.connect(
        splash.on_init_step, Qt.ConnectionType.QueuedConnection
    )

    def _set_flow_controls(enabled: bool) -> None:
        if not enabled and not runtime.get("startup_done", False):
            return
        main._run_button.setEnabled(enabled)
        main._revert_button.setEnabled(enabled)
        main._ai_setup_button.setEnabled(enabled)

    _set_flow_controls(False)

    def _on_step(name: str, status: str) -> None:
        try:
            log.debug("GUI Startup step: %s status=%s", name, status)
            label = (
                f"{name}: failed (continuing)"
                if status == "fail"
                else f"{name}…"
            )
            main.status_bar_widget.set_state("run", label)
        except Exception as exc:
            log.error("_on_step EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

    def _on_finished(startup_lhm) -> None:
        log.info(
            "GUI Startup: _on_finished entry (lhm=%s)",
            "yes" if startup_lhm else "no",
        )
        runtime["startup_done"] = True
        runtime["lhm"] = startup_lhm

        # Load pre-collected specs (written by StartupOrchestrator Step 3)
        preloaded_specs: dict = {}
        if orchestrator.specs_path:
            try:
                import json as _json
                with open(orchestrator.specs_path, encoding="utf-8") as _f:
                    preloaded_specs = _json.load(_f)
            except Exception:
                pass
        runtime["preloaded_specs"] = preloaded_specs

        # Monitor card wiring is deliberately NOT done here. In the bundled
        # PyInstaller exe, work scheduled from inside splash.exec()'s nested
        # event loop and expected to fire after that loop ends (either via
        # QTimer.singleShot or any cross-loop event hop) is silently
        # dropped. The wiring is performed directly after main.show() in
        # run() — see the block right before `return app.exec()`.

        try:
            if runtime.get("pipeline_thread") is None and runtime.get("revert_thread") is None:
                _set_flow_controls(True)
        except Exception:
            pass
        try:
            main.status_bar_widget.set_state("ok", "Idle")
            # Start dashboard polling now that LHM is ready
            log.info(
                "GUI Startup: invoking dashboard.start_polling(lhm=%s)",
                "yes" if startup_lhm else "no",
            )
            main._dashboard.start_polling(lhm=startup_lhm)
            chart = main._dashboard.thermal_chart
            if startup_lhm is None:
                chart.set_offline("Thermal monitor unavailable")
        except Exception as exc:
            log.error("_on_finished EXC: %s: %r", type(exc).__name__, exc, exc_info=True)
        log.info("GUI Startup: _on_finished exit")

    def _refresh_monitor_card() -> None:
        try:
            from src.collectors.sub.monitor_dumper import get_monitor_refresh_capabilities
            displays = get_monitor_refresh_capabilities()
            main._dashboard.set_monitor_data(displays)
            sp = runtime.get("preloaded_specs", {}) or {}
            sp["DisplayCapabilities"] = displays
            runtime["preloaded_specs"] = sp
        except Exception as exc:
            log.warning("Could not refresh monitor card: %s", exc)

    def _on_monitor_fix_requested(device: str) -> None:
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
        fix_thread.finished.connect(_refresh_monitor_card)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        runtime["monitor_fix_thread"] = fix_thread
        runtime["monitor_fix_worker"] = fix_worker
        fix_thread.finished.connect(lambda: runtime.pop("monitor_fix_thread", None))
        fix_thread.finished.connect(lambda: runtime.pop("monitor_fix_worker", None))
        fix_thread.start()

    # -- Pipeline run wiring ----------------------------------------------

    def _show_approval_dialog(action_text: str) -> None:
        dialog = ApprovalDialog(action_text, parent=main)
        approved = bool(dialog.exec())
        bridge.deliver_answer(approved)

    def _show_confirm_dialog(title: str, description: str) -> None:
        dialog = ConfirmDialog(title, description, parent=main)
        confirmed = bool(dialog.exec())
        bridge.deliver_answer(confirmed)

    def _show_batch_dialog(proposals: list) -> None:
        dialog = BatchSelectionDialog(proposals, parent=main)
        dialog.exec()
        bridge.deliver_answer(dialog.selected_indices())

    def _on_pipeline_output(text: str) -> None:
        for raw in text.splitlines():
            line = ansi_re.sub("", raw).strip()
            if line:
                main.status_bar_widget.set_state("run", line[:80])
            try:
                main._output_panel.append_line(raw)
            except Exception:
                pass

    def _on_progress_changed(percent: int, label: str) -> None:
        main._progress_bar.setValue(percent)
        main._progress_label.setText(label)
        if not main._progress_bar.isVisible():
            main._progress_bar.setVisible(True)
            main._progress_label.setVisible(True)

    def _on_benchmark_score(phase: str, scores: object, cpu_peak: object) -> None:
        try:
            main.update_benchmark_score(
                phase,
                scores if isinstance(scores, dict) else {},
                cpu_peak if isinstance(cpu_peak, (int, float)) else None,
            )
        except Exception:
            pass

    def _on_benchmark_started() -> None:
        try:
            main._benchmark_row.set_benchmark_started()
        except Exception:
            pass

    def _on_benchmark_started() -> None:
        try:
            main._benchmark_row.set_benchmark_started()
        except Exception:
            pass

    # TODO: remove after run() is next rewritten — alias makes the stale
    # bridge.signals.phase_changed.connect(_on_phase_changed) line a no-op.
    _on_phase_changed = _on_benchmark_score

    bridge.signals.progress_changed.connect(_on_progress_changed)
    bridge.signals.approval_requested.connect(_show_approval_dialog)
    bridge.signals.confirm_requested.connect(_show_confirm_dialog)
    bridge.signals.batch_selection_requested.connect(_show_batch_dialog)
    bridge.signals.output_emitted.connect(_on_pipeline_output)
    bridge.signals.phase_changed.connect(_on_phase_changed)

    bridge.signals.benchmark_score_ready.connect(_on_benchmark_score)

    bridge.signals.benchmark_started.connect(_on_benchmark_started)

    def _start_pipeline() -> None:
        if runtime.get("pipeline_thread") is not None:
            return
        if runtime.get("lhm") is None:
            main.status_bar_widget.set_state("ok", "Startup still in progress — please wait…")
            return
        log.info("Pipeline: start requested")
        _set_flow_controls(False)
        main.show_output()
        main.set_running(True)
        main._output_panel.clear_log()
        main._benchmark_row.reset()
        main.status_bar_widget.set_state("run", "Pipeline starting…")

        pipeline_thread = QThread()
        pipeline_worker = PipelineWorker(lhm=runtime["lhm"], llm=None, preloaded_specs=runtime.get("preloaded_specs", {}))
        pipeline_worker.moveToThread(pipeline_thread)
        pipeline_thread.started.connect(pipeline_worker.run)

        def _on_pipeline_started() -> None:
            log.info("Pipeline: started")
            main.status_bar_widget.set_state("run", "Pipeline running…")
            main._dashboard.pause_polling()
            main._benchmark_row.set_pipeline_running()

        def _on_pipeline_finished() -> None:
            log.info("Pipeline: finished (PASS)")
            main.status_bar_widget.set_state("ok", "Pipeline finished")
            main._dashboard.resume_polling()
            main._benchmark_row.set_pipeline_complete()
            pipeline_thread.quit()

        def _on_pipeline_failed(exc_type: str, msg: str, tb: str) -> None:
            log.error("Pipeline: failed -- %s: %s\n%s", exc_type, msg, tb)
            main.status_bar_widget.set_state("ok", f"Pipeline failed: {exc_type}")
            main._dashboard.resume_polling()
            main._benchmark_row.set_pipeline_failed()
            pipeline_thread.quit()

        def _on_thread_done() -> None:
            _set_flow_controls(True)
            main.set_running(False)
            runtime["pipeline_thread"] = None
            runtime["pipeline_worker"] = None
            main._progress_bar.setVisible(False)
            main._progress_label.setVisible(False)
            pipeline_worker.deleteLater()
            pipeline_thread.deleteLater()

        pipeline_worker.pipeline_started.connect(_on_pipeline_started)
        pipeline_worker.pipeline_finished.connect(_on_pipeline_finished)
        pipeline_worker.pipeline_failed.connect(_on_pipeline_failed)
        pipeline_thread.finished.connect(_on_thread_done)

        runtime["pipeline_thread"] = pipeline_thread
        runtime["pipeline_worker"] = pipeline_worker
        pipeline_thread.start()

    main._run_button.clicked.connect(_start_pipeline)

    # -- Revert wiring ----------------------------------------------------

    def _start_revert() -> None:
        if runtime.get("revert_thread") is not None:
            return
        from src.utils.revert import load_manifest
        if load_manifest() is None:
            main.status_bar_widget.set_state("ok", "No session backup found — nothing to revert")
            return

        _set_flow_controls(False)
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
            _set_flow_controls(True)
            runtime["revert_thread"] = None
            runtime["revert_worker"] = None
            revert_worker.deleteLater()
            revert_thread.deleteLater()

        revert_worker.revert_finished.connect(_on_revert_finished)
        revert_worker.revert_failed.connect(_on_revert_failed)
        revert_thread.finished.connect(_on_revert_thread_done)

        runtime["revert_thread"] = revert_thread
        runtime["revert_worker"] = revert_worker
        revert_thread.start()

    main._revert_button.clicked.connect(_start_revert)

    # -- AI Setup wiring --------------------------------------------------

    def _open_ai_setup() -> None:
        from src.gui.widgets.ai_setup_dialog import AISetupDialog
        dialog = AISetupDialog(parent=main)
        dialog.exec()

    main._ai_setup_button.clicked.connect(_open_ai_setup)

    # -- Cleanup ----------------------------------------------------------

    def _on_about_to_quit() -> None:
        # Cancel-on-quit: signal the worker, drain any pending dialog loop
        # to break a potential deadlock (main waits for worker; worker waits
        # for main to deliver a dialog answer), then wait for the thread to
        # exit before tearing down LHM. Test plan: "Window close (X) during
        # running pipeline → triggers cancel signal; LHM sidecar cleaned up
        # via aboutToQuit."
        pipeline_worker = runtime.get("pipeline_worker")
        pipeline_thread = runtime.get("pipeline_thread")
        if pipeline_worker is not None and pipeline_thread is not None:
            try:
                pipeline_worker.request_cancel()
                bridge.abort_pending()
                pipeline_thread.wait(5000)
            except Exception:
                log.warning("Pipeline cancel-on-quit failed", exc_info=True)

        revert_thread = runtime.get("revert_thread")
        if revert_thread is not None:
            try:
                bridge.abort_pending()
                revert_thread.wait(5000)
            except Exception:
                pass

        try:
            main._dashboard.stop_polling()
        except Exception:
            pass
        try:
            from src.pipeline.post_run_cleanup import post_run_cleanup
            post_run_cleanup(
                runtime["lhm"],
                pawnio_was_preinstalled=pawnio_was_preinstalled,
            )
        except Exception:
            pass
        try:
            settings.save_geometry(main)
        except Exception:
            pass

    app.aboutToQuit.connect(_on_about_to_quit)
    orchestrator.init_step.connect(_on_step, Qt.ConnectionType.QueuedConnection)
    orchestrator.finished.connect(_on_finished, Qt.ConnectionType.QueuedConnection)
    thread.start()

    # Splash runs first; main window appears only after startup completes
    splash.exec()
    main.show()

    # Wire monitor card AFTER main.show() returns. In the bundled exe,
    # QTimer.singleShot scheduled during splash.exec()'s nested event loop
    # is dropped when the loop ends — the timer event does not survive the
    # splash.exec() -> app.exec() handoff (worker-thread QTimers are fine
    # because they never bridge event loops). Pump the queue once so the
    # show event propagates before set_monitor_data inspects layout state,
    # and guard on startup_done in case the user dismissed splash before
    # the orchestrator finished. _refresh_monitor_card and
    # _on_monitor_fix_requested are nested closures of run() defined
    # earlier and remain in scope here.
    app.processEvents()

    if not runtime.get("startup_done"):
        log.info("GUI Startup: skipping monitor wiring (startup did not complete)")
    else:
        log.info("GUI Startup: wiring monitor card (after main.show())")
        _specs = runtime.get("preloaded_specs", {}) or {}
        try:
            main._dashboard.set_monitor_data(_specs.get("DisplayCapabilities", []))
            main._dashboard.monitor_fix_requested.connect(_on_monitor_fix_requested)
            main._dashboard.monitor_refresh_requested.connect(_refresh_monitor_card)
        except Exception as exc:
            log.warning("Could not wire monitor card: %s", exc, exc_info=True)

    return app.exec()
