"""Pipeline-worker → main-thread signal definitions.

All cross-thread communication between the QThread pipeline worker and
the main (GUI) thread funnels through this single signal bag, so the
bridge has one well-defined seam to wire dialogs, output streaming,
and lifecycle events.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class PipelineSignals(QObject):
    """Signal bag emitted by ``PipelineWorker`` and consumed by the main window."""

    output_emitted = Signal(str)
    approval_requested = Signal(str)
    confirm_requested = Signal(str, str)
    batch_selection_requested = Signal(list)
    mouse_ready_requested = Signal()

    mouse_poll_result_ready = Signal(object)
    benchmark_started = Signal()
    benchmark_score_ready = Signal(str, object, object)
    progress_changed = Signal(int, str)
    pipeline_started = Signal()
    pipeline_finished = Signal()
    pipeline_failed = Signal(str, str, str)
    init_step = Signal(str, str)
