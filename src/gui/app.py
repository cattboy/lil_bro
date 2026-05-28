"""GUI entry point — QApplication + theme + splash + main window orchestration.

Called from ``src/main.py`` when ``--terminal`` is *not* set. Owns the
application object lifecycle and wires the splash → startup orchestrator →
main window handoff.

``run()`` is the orchestration spine: it builds the QApplication, theme,
splash and main window, constructs the two controllers
(``PipelineController`` + ``StartupCoordinator``) that own the former
closure logic, connects the bridge / nav-button / orchestrator signals to
their methods, and runs the event loop.
"""

from __future__ import annotations

import sys
import threading

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication

from src.gui import theme
from src.gui.bridge import GuiBridge
from src.gui.pipeline_controller import PipelineController
from src.gui.signals import PipelineSignals
from src.gui.startup import StartupOrchestrator
from src.gui.startup_coordinator import StartupCompleter, StartupCoordinator
from src.gui.windows.main_window import MainWindow


def _install_exception_hooks(log) -> None:
    """Route uncaught main-thread and worker-thread exceptions to the debug log."""
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


def _run_app_cleanup(main, bridge, runtime: dict, log, settings,
                     pawnio_was_preinstalled: bool) -> None:
    """``aboutToQuit`` handler — cancel running work, stop polling, clean up LHM.

    Cancel-on-quit: signal the worker, drain any pending dialog loop to break
    a potential deadlock (main waits for worker; worker waits for main to
    deliver a dialog answer), then wait for the thread to exit before tearing
    down LHM. Test plan: "Window close (X) during running pipeline → triggers
    cancel signal; LHM sidecar cleaned up via aboutToQuit."
    """
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
            pass  # safe: revert-on-quit best-effort; thread may already be done

    # Wait for an in-flight dashboard monitor fix so we don't tear down LHM /
    # the manifest writer while _MonitorFixWorker is mid execute_fix(). The
    # atomic-write in revert._write_manifest survives a hard kill; this wait
    # still lets the worker land its append cleanly so the user's "Fix Now"
    # click is reflected in the next session's Revert.
    monitor_fix_thread = runtime.get("monitor_fix_thread")
    if monitor_fix_thread is not None:
        try:
            monitor_fix_thread.wait(3000)
        except Exception:
            pass  # safe: monitor-fix-on-quit best-effort

    # Wait for an in-flight monitor refresh (200-800 ms ctypes
    # EnumDisplayDevicesW probe) so we don't tear down Qt while the
    # worker thread is mid-syscall. Short wait -- this is read-only work,
    # not a system mutation.
    monitor_refresh_thread = runtime.get("monitor_refresh_thread")
    if monitor_refresh_thread is not None:
        try:
            monitor_refresh_thread.wait(2000)
        except Exception:
            pass  # safe: monitor-refresh-on-quit best-effort

    try:
        main._dashboard.stop_polling()
    except Exception:
        pass  # safe: polling worker may already be stopped or never started
    try:
        from src.pipeline.post_run_cleanup import post_run_cleanup
        post_run_cleanup(
            runtime["lhm"],
            pawnio_was_preinstalled=pawnio_was_preinstalled,
        )
    except Exception:
        pass  # safe: cleanup is best-effort on quit; failures should not block shutdown
    try:
        settings.save_geometry(main)
    except Exception:
        pass  # safe: QSettings write failure should not block window close  # safe: QSettings write failure should not block window close  # safe: QSettings write failure should not block window close


def run(debug: bool = False) -> int:
    """Boot the GUI. Returns the QApplication exit code."""
    import logging
    import re
    import secrets
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger

    level = logging.DEBUG if debug else logging.INFO
    enable_debug_logging(level=level)
    log = get_debug_logger()
    _install_exception_hooks(log)

    log.debug("GUI Startup: app.run() entry")

    from src.utils.pawnio_check import is_pawnio_installed
    try:
        pawnio_was_preinstalled = is_pawnio_installed()
    except Exception:
        pawnio_was_preinstalled = False

    ansi_re = re.compile(r"\x1b\[[0-9;]*m")

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

    # ── Controllers ────────────────────────────────────────────────────
    # The shared `runtime` dict is passed by reference to both controllers —
    # they and the wiring below all observe the same pipeline/revert state.
    pipeline = PipelineController(main, bridge, runtime, log, ansi_re)
    startup = StartupCoordinator(main, runtime, log, orchestrator, pipeline)
    runtime["_pipeline_controller"] = pipeline
    runtime["_startup_coordinator"] = startup

    pipeline.set_flow_controls(False)

    # ── Bridge signal wiring ───────────────────────────────────────────
    bridge.signals.progress_changed.connect(pipeline.on_progress_changed)
    bridge.signals.approval_requested.connect(pipeline.show_approval_dialog)
    bridge.signals.confirm_requested.connect(pipeline.show_confirm_dialog)
    bridge.signals.batch_selection_requested.connect(pipeline.show_batch_dialog)
    bridge.signals.output_emitted.connect(pipeline.on_pipeline_output)
    bridge.signals.benchmark_score_ready.connect(pipeline.on_benchmark_score)
    bridge.signals.benchmark_started.connect(pipeline.on_benchmark_started)
    bridge.signals.mouse_ready_requested.connect(pipeline.show_mouse_ready_dialog)
    bridge.signals.mouse_poll_result_ready.connect(pipeline.on_mouse_poll_result)

    # Mirror every Dashboard poll snapshot onto the optimization view's
    # LiveStatRow so both views render the identical system stats.
    main._dashboard.stats_ready.connect(main._live_stat_row.apply_snapshot)

    # ── Nav button wiring ──────────────────────────────────────────────
    main._run_button.clicked.connect(pipeline.start_pipeline)
    main._revert_button.clicked.connect(pipeline.start_revert)
    main._ai_setup_button.clicked.connect(pipeline.open_ai_setup)

    app.aboutToQuit.connect(
        lambda: _run_app_cleanup(main, bridge, runtime, log, settings, pawnio_was_preinstalled)
    )

    # ── Orchestrator → StartupCoordinator wiring ───────────────────────
    orchestrator.init_step.connect(startup.on_step, Qt.ConnectionType.QueuedConnection)

    # lhm_ready / finished route through a QObject helper parented to main so
    # the QueuedConnection has a guaranteed main-thread receiver. lhm_ready
    # fires at orchestrator Step 1 so dashboard polling starts early — while
    # the splash still shows later steps — so cards are populated by close.
    completer_lhm = StartupCompleter(startup.on_lhm_ready, parent=main)
    runtime["_lhm_completer"] = completer_lhm
    orchestrator.lhm_ready.connect(completer_lhm.on_finished, Qt.ConnectionType.QueuedConnection)

    completer_done = StartupCompleter(startup.on_finished, parent=main)
    runtime["_startup_completer"] = completer_done
    orchestrator.finished.connect(completer_done.on_finished, Qt.ConnectionType.QueuedConnection)
    thread.start()

    # Splash runs first; main window appears only after startup completes
    splash.exec()
    main.show()

    # Pump the queue once so the show event propagates and any already-queued
    # completer.on_finished event is delivered before we check startup_done.
    app.processEvents()

    if not runtime.get("startup_done"):
        # Slow-path: on_finished has not fired yet. It will wire the monitor
        # card itself when it does (the late-fire block at the end of
        # StartupCoordinator.on_finished). Cards stay in their loading state.
        log.info("GUI Startup: monitor wiring deferred (orchestrator still finishing)")
    else:
        log.info("GUI Startup: wiring monitor card (after main.show())")
        _specs = runtime.get("preloaded_specs", {}) or {}
        try:
            main._dashboard.set_monitor_data(_specs.get("DisplayCapabilities", []))
            main._dashboard.monitor_fix_requested.connect(startup.on_monitor_fix_requested)
            main._dashboard.monitor_refresh_requested.connect(startup.refresh_monitor_card)
            runtime["_monitor_wired"] = True
        except Exception as exc:
            log.warning("Could not wire monitor card: %s", exc, exc_info=True)

    return app.exec()
