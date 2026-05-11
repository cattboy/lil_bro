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

    from PySide6.QtCore import QTimer

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
        log.debug("GUI Startup: _on_finished entry")
        runtime["startup_done"] = True
        runtime["lhm"] = startup_lhm
        try:
            if runtime.get("pipeline_thread") is None and runtime.get("revert_thread") is None:
                _set_flow_controls(True)
        except Exception:
            pass
        try:
            main.status_bar_widget.set_state("ok", "Idle")
            # Start dashboard polling now that LHM is ready
            main._dashboard.start_polling(lhm=startup_lhm)
            chart = main._dashboard.thermal_chart
            if startup_lhm is None:
                chart.set_offline("Thermal monitor unavailable")
        except Exception as exc:
            log.error("_on_finished EXC: %s: %r", type(exc).__name__, exc, exc_info=True)
        log.debug("GUI Startup: _on_finished exit")

    # -- Pipeline run wiring ----------------------------------------------

    def _show_approval_dialog(action_text: str) -> None:
        dialog = ApprovalDialog(action_text, parent=main)
        approved = bool(dialog.exec())
        bridge.deliver_answer(approved)

    def _show_confirm_dialog(question: str) -> None:
        dialog = ConfirmDialog(question, parent=main)
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

    def _on_phase_changed(phase_name: str, status: str) -> None:
        try:
            main.update_phase(phase_name, status)
        except Exception:
            pass

    bridge.signals.progress_changed.connect(_on_progress_changed)
    bridge.signals.approval_requested.connect(_show_approval_dialog)
    bridge.signals.confirm_requested.connect(_show_confirm_dialog)
    bridge.signals.batch_selection_requested.connect(_show_batch_dialog)
    bridge.signals.output_emitted.connect(_on_pipeline_output)
    bridge.signals.phase_changed.connect(_on_phase_changed)

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
        main._phase_row.reset()
        main.status_bar_widget.set_state("run", "Pipeline starting…")

        pipeline_thread = QThread()
        pipeline_worker = PipelineWorker(lhm=runtime["lhm"], llm=None)
        pipeline_worker.moveToThread(pipeline_thread)
        pipeline_thread.started.connect(pipeline_worker.run)

        def _on_pipeline_started() -> None:
            log.info("Pipeline: started")
            main.status_bar_widget.set_state("run", "Pipeline running…")

        def _on_pipeline_finished() -> None:
            log.info("Pipeline: finished (PASS)")
            main.status_bar_widget.set_state("ok", "Pipeline finished")
            pipeline_thread.quit()

        def _on_pipeline_failed(exc_type: str, msg: str, tb: str) -> None:
            log.error("Pipeline: failed -- %s: %s\n%s", exc_type, msg, tb)
            main.status_bar_widget.set_state("ok", f"Pipeline failed: {exc_type}")
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

    return app.exec()
