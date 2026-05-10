"""StartupOrchestrator — runs the slow init steps off the main thread.

Decouples the splash lifecycle from blocking ``main()`` calls. The LHM
sidecar startup, font registration, and any future warm-up steps run
inside a worker QThread; the orchestrator emits ``init_step(name,
status)`` signals consumed by the splash widget so users see what the
program is doing during the 3-9 sec cold-start gap.

When everything completes, ``finished(startup_lhm)`` fires; ``app.run``
uses that signal to swap the splash for the main window.
"""

from __future__ import annotations


from PySide6.QtCore import QObject, QThread, Signal


class StartupOrchestrator(QObject):
    """Runs LHM init + font registration + (future) warm-up steps."""

    init_step = Signal(str, str)  # step_name, "running" | "ok" | "fail"
    finished = Signal(object)     # startup_lhm tuple or None on partial failure

    def run(self) -> None:
        startup_lhm = None
        try:
            self.init_step.emit("Initializing UI", "running")
            from src.gui import theme
            theme.load_fonts()
            self.init_step.emit("Initializing UI", "ok")

            self.init_step.emit("Starting thermal monitor", "running")
            try:
                from src.pipeline.startup_thermals import run_startup_thermal_scan
                startup_lhm, _ = run_startup_thermal_scan()
                self.init_step.emit("Starting thermal monitor", "ok")
            except Exception:
                self.init_step.emit("Starting thermal monitor", "fail")

            self.init_step.emit("Ready", "ok")
        except Exception:
            from src.utils.debug_logger import get_debug_logger
            get_debug_logger().error("StartupOrchestrator unhandled exception", exc_info=True)
        finally:
            self.finished.emit(startup_lhm)


def run_startup_in_thread(parent: QObject | None = None) -> tuple[QThread, StartupOrchestrator]:
    """Spin up a worker thread + orchestrator, ready to ``thread.start()``."""
    thread = QThread(parent)
    orchestrator = StartupOrchestrator()
    orchestrator.moveToThread(thread)
    thread.started.connect(orchestrator.run)
    orchestrator.finished.connect(thread.quit)
    return thread, orchestrator
