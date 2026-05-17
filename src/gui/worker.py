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

from PySide6.QtCore import QObject, Signal


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
