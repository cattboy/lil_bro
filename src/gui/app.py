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

    from src.agent_tools.thermal_guidance import derive_cpu_temp, derive_gpu_temp
    from src.benchmarks.thermal_monitor import fetch_snapshot
    from src.gui.widgets.approval_dialog import ApprovalDialog
    from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
    from src.gui.widgets.confirm_dialog import ConfirmDialog
    from src.gui.worker import PipelineWorker, RevertWorker
    from src.utils.pawnio_check import is_pawnio_installed

    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    log.debug("GUI Startup: app.run() entry")

    # Capture PawnIO state BEFORE the worker thread launches the LHM
    # sidecar (which may install PawnIO). The CLI does the same in
    # src/main.py so post_run_cleanup leaves the user's pre-existing
    # PawnIO install in place.
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

    log.debug("GUI Startup: main.show before")
    main.show()
    log.debug("GUI Startup: main.show after")

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

    # All flow controls start disabled until startup completes.
    def _set_flow_controls(enabled: bool) -> None:
        main._run_button.setEnabled(enabled)
        main.action_run_pipeline.setEnabled(enabled)
        main.action_revert.setEnabled(enabled)

    _set_flow_controls(False)

    def _on_step(name: str, status: str) -> None:
        try:
            log.debug("GUI Startup step: %s status=%s", name, status)
            label = (
                f"{name}: failed (continuing)"
                if status == "fail"
                else f"{name}…"
            )
            main.statusBar().showMessage(label)
        except Exception as exc:
            log.error("_on_step EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

    def _on_finished(startup_lhm) -> None:
        log.debug("GUI Startup: _on_finished entry")
        runtime["lhm"] = startup_lhm
        # Re-enable all flow controls OUTSIDE the chart try-block so any
        # later chart/state failure can't strand them disabled.
        try:
            _set_flow_controls(True)
        except Exception:
            pass
        try:
            main.statusBar().showMessage("Ready")
            chart = getattr(main, "thermal_chart", None)
            if chart is not None and startup_lhm is None:
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
                main.statusBar().showMessage(line)

    bridge.signals.approval_requested.connect(_show_approval_dialog)
    bridge.signals.confirm_requested.connect(_show_confirm_dialog)
    bridge.signals.batch_selection_requested.connect(_show_batch_dialog)
    bridge.signals.output_emitted.connect(_on_pipeline_output)

    def _start_pipeline() -> None:
        if runtime.get("pipeline_thread") is not None:
            return
        log.info("Pipeline: start requested")
        _set_flow_controls(False)
        main.statusBar().showMessage("Pipeline starting…")

        pipeline_thread = QThread()
        pipeline_worker = PipelineWorker(lhm=runtime["lhm"], llm=None)
        pipeline_worker.moveToThread(pipeline_thread)
        pipeline_thread.started.connect(pipeline_worker.run)

        def _on_pipeline_started() -> None:
            log.info("Pipeline: started")
            main.statusBar().showMessage("Pipeline running…")

        def _on_pipeline_finished() -> None:
            log.info("Pipeline: finished (PASS)")
            main.statusBar().showMessage("Pipeline finished")
            pipeline_thread.quit()

        def _on_pipeline_failed(exc_type: str, msg: str, tb: str) -> None:
            log.error("Pipeline: failed -- %s: %s\n%s", exc_type, msg, tb)
            main.statusBar().showMessage(f"Pipeline failed: {exc_type}: {msg}")
            pipeline_thread.quit()

        def _on_thread_done() -> None:
            _set_flow_controls(True)
            runtime["pipeline_thread"] = None
            runtime["pipeline_worker"] = None
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
    main.action_run_pipeline.triggered.connect(_start_pipeline)

    # -- Revert wiring ----------------------------------------------------

    def _start_revert() -> None:
        if runtime.get("revert_thread") is not None:
            return
        # Quick pre-check on main thread (file read only -- safe).
        from src.utils.revert import load_manifest
        if load_manifest() is None:
            main.statusBar().showMessage("No session backup found -- nothing to revert")
            return

        _set_flow_controls(False)
        main.statusBar().showMessage("Reverting session…")

        revert_thread = QThread()
        revert_worker = RevertWorker()
        revert_worker.moveToThread(revert_thread)
        revert_thread.started.connect(revert_worker.run)

        def _on_revert_finished() -> None:
            main.statusBar().showMessage("Revert complete")
            revert_thread.quit()

        def _on_revert_failed(exc_type: str, msg: str, tb: str) -> None:
            log.error("Revert: GUI revert failed -- %s: %s\n%s", exc_type, msg, tb)
            main.statusBar().showMessage(f"Revert failed: {exc_type}: {msg}")
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

    main.action_revert.triggered.connect(_start_revert)

    # Thermal polling -- uses the real working API (fetch_snapshot from
    # benchmarks.thermal_monitor + derive_*_temp from
    # agent_tools.thermal_guidance). LHMSidecar.read_latest() does not
    # exist; quick_status._read_temp's call to it always falls into
    # except (note the # type: ignore at that call site).
    # Timer starts unconditionally and no-ops until ``runtime["lhm"]``
    # is populated by ``_on_finished``.
    thermal_timer = QTimer(app)
    thermal_timer.setInterval(2000)

    def _poll_thermal() -> None:
        chart = getattr(main, "thermal_chart", None)
        if chart is None or runtime.get("lhm") is None:
            return
        try:
            snap = fetch_snapshot()
            cpu_c = derive_cpu_temp(snap) if snap else None
            gpu_c = derive_gpu_temp(snap) if snap else None
        except Exception:
            chart.set_offline("Thermal read failed")
            return
        if cpu_c is None and gpu_c is None:
            chart.set_offline("No sensor data")
            return
        chart.append_sample(cpu_c, gpu_c)

    thermal_timer.timeout.connect(_poll_thermal)
    thermal_timer.start()

    def _on_about_to_quit() -> None:
        try:
            thermal_timer.stop()
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

    return app.exec()
