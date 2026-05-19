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
    lhm_ready = Signal(object)    # emitted from worker thread after Step 1 succeeds
    finished = Signal(object)     # startup_lhm tuple or None on partial failure

    def run(self) -> None:
        from src.collectors.sub.lhm_sidecar import LHMSidecar
        from src.agent_tools.thermal_guidance import derive_cpu_temp
        from src.benchmarks.thermal_monitor import fetch_snapshot
        from src.pipeline.startup_thermals import _SENSOR_RETRIES, _SENSOR_RETRY_DELAY
        from time import sleep

        self.specs_path: str | None = None
        startup_lhm = None
        try:
            # ── Step 1: LHM Monitor — PawnIO install + sidecar launch ───────
            self.init_step.emit("LHM Monitor", "running")
            lhm = LHMSidecar()
            lhm_available = False
            try:
                lhm_available = lhm.start()
                self.init_step.emit("LHM Monitor", "done" if lhm_available else "fail")
                if lhm_available:
                    startup_lhm = lhm
                    # Trigger dashboard polling now so by splash-close the cards
                    # are already populated. See plan
                    # `when-starting-lil-bro-exe-sometimes-smooth-puzzle.md`.
                    self.lhm_ready.emit(lhm)
            except Exception:
                self.init_step.emit("LHM Monitor", "fail")

            # ── Step 2: Sensors — wait for CPU/GPU readings to appear ───────
            self.init_step.emit("Sensors", "running")
            if lhm_available:
                try:
                    for _ in range(_SENSOR_RETRIES):
                        temps = fetch_snapshot()
                        if temps and derive_cpu_temp(temps) is not None:
                            break
                        sleep(_SENSOR_RETRY_DELAY)
                except Exception:
                    pass
            self.init_step.emit("Sensors", "done")

            # ── Step 3: System Specs — collect full hardware profile ─────────
            self.init_step.emit("System Specs", "running")
            try:
                from src.collectors.spec_dumper import dump_system_specs
                path = dump_system_specs()
                self.specs_path = path if path else None
                self.init_step.emit("System Specs", "done" if path else "fail")
            except Exception:
                self.specs_path = None
                self.init_step.emit("System Specs", "fail")

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
