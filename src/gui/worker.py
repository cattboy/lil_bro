"""PipelineWorker — QObject that runs the 5-phase pipeline on a worker thread.

Signal flow::

    main thread          worker thread (QThread)
    ───────────          ───────────────────────
    thread.start() ────► worker.run()
                              │
                              ├─ pipeline_started.emit()
                              │
                              ├─ run_optimization_pipeline(...)
                              │     │
                              │     ├─ phases poll _state.is_cancelled()
                              │     ├─ formatting._DEFAULT_SINK     → output_emitted
                              │     ├─ formatting._APPROVAL_HANDLER → bridge dialog
                              │     ├─ formatting._CONFIRM_HANDLER  → bridge dialog
                              │     └─ progress_bar._PROGRESS_SINK  → progress_changed
                              │
                              ├─ pipeline_finished.emit() OR
                              └─ pipeline_failed.emit(exc_type, msg, traceback)

Cooperative cancel: the main thread calls ``worker.request_cancel()``;
the worker installs a cancel check on ``_state`` so phases can poll it
between work units. Cinebench is not graceful-cancellable — documented.
"""

from __future__ import annotations

import traceback
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal

# SystemStatsWorker poll cadence — the shared dashboard / LiveStatRow stats feed.
_POLL_INTERVAL_MS = 5000


class PipelineWorker(QObject):
    """Wraps run_optimization_pipeline for a QThread.

    Move this object onto a QThread, connect ``thread.started`` to
    ``run`` and ``pipeline_finished`` / ``pipeline_failed`` to
    ``thread.quit``, then start the thread.
    """

    pipeline_started = Signal()
    pipeline_finished = Signal()
    pipeline_failed = Signal(str, str, str)  # exc_type, message, traceback

    def __init__(self, lhm: Any = None, llm: Any = None, preloaded_specs: dict | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._lhm = lhm
        self._llm = llm
        self._preloaded_specs = preloaded_specs or {}
        self._cancel_requested = False

    @property
    def cancel_requested(self) -> bool:
        return self._cancel_requested

    def request_cancel(self) -> None:
        """Cooperative cancel — phases poll this between work units."""
        self._cancel_requested = True

    def run(self) -> None:
        from src.pipeline import _state
        _state.set_cancel_check(lambda: self._cancel_requested)
        try:
            self.pipeline_started.emit()
            from src.pipeline.phases import run_optimization_pipeline
            run_optimization_pipeline(self._lhm, self._llm, preloaded_specs=self._preloaded_specs)
        except Exception as exc:  # pragma: no cover - dispatched to GUI
            from src.utils.debug_logger import get_debug_logger
            get_debug_logger().error("PipelineWorker uncaught exception", exc_info=True)
            self.pipeline_failed.emit(type(exc).__name__, str(exc), traceback.format_exc())
            return
        finally:
            _state.set_cancel_check(None)

        self.pipeline_finished.emit()



class _MonitorFixWorker(QObject):
    """Runs ``execute_fix('display', specs)`` off the GUI thread.

    The bridge's installed approval handler intercepts ``prompt_approval()``
    inside ``_fix_display()`` and surfaces it via the standard ApprovalDialog,
    so this worker only needs to invoke the dispatcher.
    """

    finished = Signal()

    def __init__(self, specs: dict) -> None:
        super().__init__()
        self._specs = specs

    def run(self) -> None:
        try:
            from src.pipeline.fix_dispatch import execute_fix
            execute_fix("display", self._specs)
        except Exception:
            from src.utils.debug_logger import get_debug_logger
            get_debug_logger().error("MonitorFixWorker uncaught exception", exc_info=True)
        self.finished.emit()


class _MousePollWorker(QObject):
    """Runs ``check_polling_rate()`` off the GUI thread.

    The polling probe in ``src/agent_tools/mouse.py`` blocks for ~2 seconds
    while it samples cursor deltas. Calling it from the main thread would
    freeze the dashboard, so the dashboard's "Test Polling" button
    dispatches this worker on its own QThread and shows the result once
    ``finished`` arrives.
    """

    finished = Signal(dict)

    def run(self) -> None:
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()
        log.info("MousePollWorker: starting 2-second polling measurement")
        try:
            from src.agent_tools.mouse import check_polling_rate
            result = check_polling_rate()
        except Exception as exc:
            log.warning("MousePollWorker: failed: %s", exc, exc_info=True)
            result = {"current_hz": 0, "status": "ERROR", "message": str(exc)}
        log.info(
            "MousePollWorker: done hz=%s status=%s",
            result.get("current_hz"),
            result.get("status"),
        )
        self.finished.emit(result)


class RevertWorker(QObject):
    """Wraps run_revert_phase for a QThread."""

    revert_started = Signal()
    revert_finished = Signal()
    revert_failed = Signal(str, str, str)  # exc_type, message, traceback

    def run(self) -> None:
        try:
            self.revert_started.emit()
            from src.pipeline.phase_revert import run_revert_phase
            run_revert_phase()
        except Exception as exc:
            from src.utils.debug_logger import get_debug_logger
            get_debug_logger().error("RevertWorker uncaught exception", exc_info=True)
            self.revert_failed.emit(type(exc).__name__, str(exc), traceback.format_exc())
            return
        self.revert_finished.emit()


class SystemStatsWorker(QObject):
    """Polls system stats at 5-sec cadence on its own QThread.

    Single shared poller for both the Dashboard and the optimization view's
    ``LiveStatRow``. Uses only the pipeline-safe data subset -- psutil, a single
    ``fetch_snapshot()`` LHM read, and a light QSettings mouse-Hz read -- so it
    runs continuously (including during the optimization pipeline) without
    contending for registry / WMI / subprocess access.
    """

    snapshot_ready = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer: QTimer | None = None

    def start(self) -> None:
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()
        log.info("SystemStatsWorker.start: entering on thread %s",
                 QThread.currentThread().objectName() or "<unnamed>")
        try:
            import psutil
            psutil.cpu_percent(interval=None)  # prime baseline so first real tick isn't 0%
        except Exception:
            pass  # safe: psutil prime is best-effort; first tick will just report 0%
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._tick)
            self._timer.start(_POLL_INTERVAL_MS)
        log.info("SystemStatsWorker.start: timer armed, firing first tick now")
        self._tick()  # immediate first sample

    def _tick(self) -> None:
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()
        snap: dict = {}

        # CPU% + RAM via psutil -- fast, non-blocking, no registry/WMI contention.
        try:
            import psutil
            snap["cpu_usage"] = f"{psutil.cpu_percent(interval=None):.0f}%"
            vm = psutil.virtual_memory()
            snap["ram_used"] = f"{vm.used / 1_073_741_824:.1f} GB"
        except Exception:
            snap.setdefault("cpu_usage", "—")
            snap.setdefault("ram_used", "—")

        # Last-measured mouse Hz -- a light QSettings read (no system registry
        # or subprocess), safe to run concurrently with the pipeline.
        try:
            from src.agent_tools.quick_status import _read_mouse_hz
            snap["mouse_hz"] = _read_mouse_hz()
        except Exception:
            pass  # safe: mouse-Hz read is best-effort; tile keeps its own fallback

        # Thermal data from fetch_snapshot -- the same source the chart uses, so
        # always accurate. fetch_snapshot() returns {} when LHM is unreachable,
        # leaving the temp cards at "—".
        therm: dict = {}
        try:
            from src.agent_tools.thermal_guidance import derive_cpu_temp, derive_gpu_temp
            from src.benchmarks.thermal_monitor import fetch_snapshot
            therm = fetch_snapshot()
            if therm:
                cpu_c_f = derive_cpu_temp(therm)
                gpu_c_f = derive_gpu_temp(therm)
                if cpu_c_f is not None:
                    snap["_cpu_c"] = cpu_c_f
                    snap["cpu_temp"] = f"{int(round(cpu_c_f))}°C"
                if gpu_c_f is not None:
                    snap["_gpu_c"] = gpu_c_f
                    snap["gpu_temp"] = f"{int(round(gpu_c_f))}°C"
        except Exception as exc:
            log.warning("SystemStatsWorker._tick: thermal fetch failed: %s", exc, exc_info=True)

        # Diagnostic INFO on first 3 ticks and every 12th (≈ 1 min) -- keeps
        # the log compact but proves the polling loop is alive and surfaces
        # what fetch_snapshot returned vs. what derive_*_temp extracted.
        self._tick_count = getattr(self, "_tick_count", 0) + 1
        if self._tick_count <= 3 or self._tick_count % 12 == 0:
            sample_keys = list(therm.keys())[:3] if therm else []
            log.info(
                "SystemStatsWorker._tick #%d: therm_keys=%d sample=%s cpu_c=%s gpu_c=%s cpu_temp=%s",
                self._tick_count,
                len(therm),
                sample_keys,
                snap.get("_cpu_c"),
                snap.get("_gpu_c"),
                snap.get("cpu_temp"),
            )

        self.snapshot_ready.emit(snap)
