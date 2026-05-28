"""Verifies cooperative cancel state + worker lifecycle.

The full cancel-mid-pipeline integration is exercised manually (real
hardware) — these tests pin the unit-level invariants:

- ``_state.is_cancelled()`` returns False when no check is installed.
- A worker's ``request_cancel`` flips the flag the pipeline polls.
- ``run_optimization_pipeline`` exits without calling phase.run when
  the cancel check returns True before the loop starts.
"""

from __future__ import annotations

from unittest.mock import patch

from src.gui.worker import PipelineWorker
from src.pipeline import _state


def test_is_cancelled_default_false():
    _state.set_cancel_check(None)
    assert _state.is_cancelled() is False


def test_set_cancel_check_round_trip():
    flag = {"v": False}
    _state.set_cancel_check(lambda: flag["v"])
    try:
        assert _state.is_cancelled() is False
        flag["v"] = True
        assert _state.is_cancelled() is True
    finally:
        _state.set_cancel_check(None)


def test_worker_request_cancel_sets_flag():
    worker = PipelineWorker()
    assert worker.cancel_requested is False
    worker.request_cancel()
    assert worker.cancel_requested is True


def test_pipeline_skips_phases_when_pre_cancelled():
    """If is_cancelled() returns True before the loop, no phase.run executes."""
    from src.pipeline import phases

    _state.set_cancel_check(lambda: True)
    try:
        with patch.object(phases, "_PHASES",
                          (_RaisingPhase("must-not-run"),)):
            phases.run_optimization_pipeline(lhm=None, llm=None)
    finally:
        _state.set_cancel_check(None)


class _RaisingPhase:
    def __init__(self, name: str) -> None:
        self.name = name

    def run(self, ctx):  # pragma: no cover - guard
        raise AssertionError(f"phase {self.name} must not run when cancelled")



def test_stop_requested_reaches_worker_across_threads(qtbot):
    """Regression for the QueuedConnection deadlock bug.

    The original Stop button wiring used Qt.AutoConnection, which picks
    QueuedConnection for cross-thread signals. But PipelineWorker.run() is
    a long blocking call -- it occupies the worker thread for the full
    pipeline duration -- so the worker thread's Qt event loop never
    processes queued slots. The cancel signal sat in the queue forever.

    Fix in src/gui/app.py: explicitly use Qt.ConnectionType.DirectConnection
    so the slot runs on the SENDER (GUI) thread, writing the bool flag
    from there. The worker's polling loop reads it on the next iteration.

    Topology mirrors production: real QThread, real PipelineWorker moved
    to it, a QObject runner moved to the same thread spinning a synchronous
    polling loop. Cancel emitted from the main thread reaches the worker's
    flag within one poll interval (~50 ms).
    """
    import time
    from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

    class _Emitter(QObject):
        stop_requested = Signal()

    class _PollRunner(QObject):
        finished = Signal()

        def __init__(self, worker: PipelineWorker) -> None:
            super().__init__()
            self.worker = worker
            self.saw_cancel = False

        @Slot()
        def run(self) -> None:
            _state.set_cancel_check(lambda: self.worker.cancel_requested)
            try:
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    if _state.is_cancelled():
                        self.saw_cancel = True
                        return
                    time.sleep(0.05)
            finally:
                _state.set_cancel_check(None)
                self.finished.emit()

    emitter = _Emitter()
    worker = PipelineWorker()
    runner = _PollRunner(worker)

    thread = QThread()
    worker.moveToThread(thread)
    runner.moveToThread(thread)
    thread.started.connect(runner.run)
    runner.finished.connect(thread.quit)
    emitter.stop_requested.connect(
        worker.request_cancel,
        Qt.ConnectionType.DirectConnection,
    )

    try:
        thread.start()
        # Wait for runner to enter its polling loop.
        time.sleep(0.2)
        with qtbot.waitSignal(runner.finished, timeout=3000) as blocker:
            emitter.stop_requested.emit()
        assert blocker.signal_triggered, (
            "runner.finished never fired -- cancel signal likely "
            "deadlocked in QueuedConnection (use Qt.DirectConnection)"
        )
        assert runner.saw_cancel, (
            "polling loop never observed _state.is_cancelled() == True"
        )
    finally:
        # Hard guarantee the thread is stopped before pytestqt teardown
        # processes events on these QObjects -- otherwise a thread that
        # outlives the test triggers an access violation when pytestqt
        # walks the now-half-destroyed QObject graph.
        if thread.isRunning():
            worker.request_cancel()
            thread.quit()
            thread.wait(2000)
            if thread.isRunning():
                thread.terminate()
                thread.wait(1000)
