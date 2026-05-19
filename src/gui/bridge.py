"""Installs the GUI's handlers/sinks via the formatting + progress_bar registries.

Handler registration map::

    formatting.set_default_sink(...)      → bridge._emit_output → signals.output_emitted
    formatting.set_approval_handler(...)  → bridge._handle_approval → signals.approval_requested
    formatting.set_confirm_handler(...)   → bridge._handle_confirm  → signals.confirm_requested
    progress_bar.set_progress_sink(...)   → bridge._emit_progress  → signals.progress_changed

Approval / confirm flow (cross-thread)::

    worker thread                      main thread
    ─────────────                      ───────────
    prompt_approval(action)
       │ (handler)
       ▼
    bridge._handle_approval ──signal──► signals.approval_requested
       │                                 │
       │                                 ▼
       │                              ApprovalDialog opens
       │                                 │
       │                                 ▼
       │                            user clicks Approve / Deny / Esc
       │                                 │
       │  ◄────── bridge.deliver_answer(bool)
       │
       ▼
    QEventLoop.exec() returns → handler returns bool

Safety: ``QEventLoop.exec()`` is wrapped with a ``QTimer.singleShot``
5-minute timeout. On timeout the handler returns False ("Deny" / "No"),
so a forgotten dialog never silently approves a system change.
"""

from __future__ import annotations

from PySide6.QtCore import QEventLoop, QObject, QTimer

from src.utils import formatting, progress_bar


_DIALOG_TIMEOUT_MS = 5 * 60 * 1000  # 5 minutes


class GuiBridge(QObject):
    """Owns the install/restore lifecycle for GUI handlers + sinks."""

    def __init__(self, signals, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.signals = signals
        self._installed = False
        self._answer_callback = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def install(self) -> None:
        formatting.set_default_sink(self._emit_output)
        formatting.set_approval_handler(self._handle_approval)
        formatting.set_confirm_handler(self._handle_confirm)
        formatting.set_pause_handler(self._handle_pause)
        formatting.set_batch_selection_handler(self._handle_batch_selection)
        formatting.set_benchmark_score_sink(self._emit_benchmark_score)
        formatting.set_benchmark_started_sink(self._emit_benchmark_started)
        progress_bar.set_progress_sink(self._emit_progress)
        self._installed = True

    def restore(self) -> None:
        formatting.set_default_sink(None)
        formatting.set_approval_handler(None)
        formatting.set_confirm_handler(None)
        formatting.set_pause_handler(None)
        formatting.set_batch_selection_handler(None)
        formatting.set_benchmark_score_sink(None)
        formatting.set_benchmark_started_sink(None)
        progress_bar.set_progress_sink(None)
        self._installed = False

    @property
    def installed(self) -> bool:
        return self._installed

    # ── Sinks (worker thread → signal emit, no blocking) ───────────────

    def _emit_output(self, text: str) -> None:
        self.signals.output_emitted.emit(text)

    def _emit_progress(self, percent: int, label: str) -> None:
        self.signals.progress_changed.emit(int(percent), str(label))

    def _emit_benchmark_score(self, phase: str, scores: dict, cpu_peak: "float | None") -> None:
        self.signals.benchmark_score_ready.emit(phase, scores, cpu_peak)

    def _emit_benchmark_started(self) -> None:
        self.signals.benchmark_started.emit()

    # ── Bool-answer handlers (worker thread blocks until main answers) ──

    def _handle_approval(self, action: str) -> bool:
        return self._await_bool_answer(self.signals.approval_requested, action)

    def _handle_confirm(self, title: str, description: str = "") -> bool:
        return self._await_bool_answer(self.signals.confirm_requested, title, description)

    def _await_bool_answer(self, signal, *payload) -> bool:
        loop = QEventLoop()
        result = {"value": False}  # safe default = "Deny" / "No"

        def _on_answer(answer: bool) -> None:
            result["value"] = bool(answer)
            loop.quit()

        self._answer_callback = _on_answer
        signal.emit(*payload)
        QTimer.singleShot(_DIALOG_TIMEOUT_MS, loop.quit)
        loop.exec()
        self._answer_callback = None
        return result["value"]

    def deliver_answer(self, value) -> None:
        """Called by the main thread (dialog accept/reject slot) to unblock the worker.

        ``value`` is bool for approval/confirm dialogs, list[int] for batch
        selection. The worker-thread callback set up in ``_await_*_answer``
        is responsible for typing it correctly.
        """
        cb = self._answer_callback
        if cb is not None:
            cb(value)

    def abort_pending(self) -> None:
        """Unblock any in-flight ``_await_*_answer`` loop so the worker thread can exit.

        Called from ``_on_about_to_quit`` before ``pipeline_thread.wait()`` to
        avoid the deadlock where the worker is parked in ``QEventLoop.exec()``
        waiting for the main thread to deliver a dialog answer that will never
        come. ``deliver_answer(False)`` is safe for both branches:

        - approval/confirm loops type-check via ``bool()`` → ``False`` = Deny / No.
        - batch-selection loop normalizes via ``list(answer or [])`` → ``[]`` = skip.
        """
        if self._answer_callback is not None:
            self.deliver_answer(False)


    # ── Pause + batch-selection handlers ───────────────────────────────

    def _handle_pause(self, message: str) -> None:
        """Auto-continue in GUI mode. CLI ``Press Enter`` prompts are no-ops here."""
        return

    def _handle_batch_selection(self, proposals: list, total: int) -> list[int]:
        """Show ``BatchSelectionDialog`` (via signal) and wait for the selection."""
        return self._await_list_answer(self.signals.batch_selection_requested, proposals)

    def _await_list_answer(self, signal, payload) -> list:
        loop = QEventLoop()
        result: dict = {"value": []}

        def _on_answer(answer) -> None:
            result["value"] = list(answer or [])
            loop.quit()

        self._answer_callback = _on_answer
        signal.emit(payload)
        QTimer.singleShot(_DIALOG_TIMEOUT_MS, loop.quit)
        loop.exec()
        self._answer_callback = None
        return result["value"]
