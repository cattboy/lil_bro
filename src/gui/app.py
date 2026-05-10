"""GUI entry point — QApplication + theme + splash + main window orchestration.

Called from ``src/main.py`` when ``--terminal`` is *not* set. Owns the
application object lifecycle, wires the splash → startup orchestrator →
main window handoff, and dismisses both PyInstaller native splash and
the QSplashScreen once startup completes.
"""

from __future__ import annotations

import sys

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
from src.utils.action_logger import action_logger


def run() -> int:
    """Boot the GUI. Returns the QApplication exit code."""
    import re

    from PySide6.QtCore import QTimer

    from src.agent_tools.thermal_guidance import derive_cpu_temp, derive_gpu_temp
    from src.benchmarks.thermal_monitor import fetch_snapshot
    from src.gui.widgets.approval_dialog import ApprovalDialog
    from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
    from src.gui.widgets.confirm_dialog import ConfirmDialog
    from src.gui.worker import PipelineWorker
    from src.utils.pawnio_check import is_pawnio_installed

    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

    action_logger.log_action("GUI Startup", "app.run() entry")

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

    action_logger.log_action("GUI Startup", "main.show before")
    main.show()
    action_logger.log_action("GUI Startup", "main.show after")

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
    }

    main._run_button.setEnabled(False)
    main.action_run_pipeline.setEnabled(False)

    def _on_step(name: str, status: str) -> None:
        try:
            action_logger.log_action(
                "GUI Startup", f"step: {name}", f"status={status}"
            )
            label = (
                f"{name}: failed (continuing)"
                if status == "fail"
                else f"{name}…"
            )
            main.statusBar().showMessage(label)
        except Exception as exc:
            action_logger.log_action(
                "GUI Startup", "_on_step EXC",
                f"{type(exc).__name__}: {exc!r}", outcome="FAIL",
            )

    def _on_finished(startup_lhm) -> None:
        action_logger.log_action("GUI Startup", "_on_finished entry")
        runtime["lhm"] = startup_lhm
        # Re-enable the Run button OUTSIDE the chart try-block so any
        # later chart/state failure can't strand it disabled.
        try:
            main._run_button.setEnabled(True)
            main.action_run_pipeline.setEnabled(True)
        except Exception:
            pass
        try:
            main.statusBar().showMessage("Ready")
            chart = getattr(main, "thermal_chart", None)
            if chart is not None and startup_lhm is None:
                chart.set_offline("Thermal monitor unavailable")
        except Exception as exc:
            action_logger.log_action(
                "GUI Startup", "_on_finished EXC",
                f"{type(exc).__name__}: {exc!r}\n{traceback.format_exc()}",
                outcome="FAIL",
            )
        action_logger.log_action("GUI Startup", "_on_finished exit")

    # ── Pipeline run wiring ──────────────────────────────────────────────

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
        action_logger.log_action("Pipeline", "start requested")
        main._run_button.setEnabled(False)
        main.action_run_pipeline.setEnabled(False)
        main.statusBar().showMessage("Pipeline starting…")

        pipeline_thread = QThread()
        pipeline_worker = PipelineWorker(lhm=runtime["lhm"], llm=None)
        pipeline_worker.moveToThread(pipeline_thread)
        pipeline_thread.started.connect(pipeline_worker.run)

        def _on_pipeline_started() -> None:
            action_logger.log_action("Pipeline", "started")
            main.statusBar().showMessage("Pipeline running…")

        def _on_pipeline_finished() -> None:
            action_logger.log_action("Pipeline", "finished", outcome="PASS")
            main.statusBar().showMessage("Pipeline finished")
            pipeline_thread.quit()

        def _on_pipeline_failed(exc_type: str, msg: str, tb: str) -> None:
            action_logger.log_action(
                "Pipeline", "failed",
                f"{exc_type}: {msg}\n{tb}", outcome="FAIL",
            )
            main.statusBar().showMessage(f"Pipeline failed: {exc_type}: {msg}")
            pipeline_thread.quit()

        def _on_thread_done() -> None:
            main._run_button.setEnabled(True)
            main.action_run_pipeline.setEnabled(True)
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

    # Thermal polling — uses the real working API (fetch_snapshot from
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
