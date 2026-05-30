"""Tests for src.gui.worker.PipelineWorker.run() signal lifecycle.

The cancel-flag unit tests (request_cancel, _state round-trip, DirectConnection
regression) already live in test_cancel_flow.py. This file covers the signal
emission contract and the cancel-check cleanup guarantee.
"""
from __future__ import annotations

from unittest.mock import patch

from src.gui.worker import PipelineWorker
from src.pipeline import _state


class TestPipelineWorkerSignals:
    def test_run_emits_started_then_finished_on_success(self):
        """Happy path: pipeline_started fires before pipeline_finished; no failed."""
        worker = PipelineWorker()
        order: list[str] = []
        worker.pipeline_started.connect(lambda: order.append("started"))
        worker.pipeline_finished.connect(lambda: order.append("finished"))
        worker.pipeline_failed.connect(lambda *a: order.append("failed"))

        with patch("src.pipeline.phases.run_optimization_pipeline"):
            worker.run()

        assert order == ["started", "finished"], f"unexpected signal order: {order}"

    def test_run_emits_failed_on_exception(self):
        """Exception inside run_optimization_pipeline must emit pipeline_failed with
        the exception type and message; pipeline_finished must NOT fire."""
        worker = PipelineWorker()
        finished: list[str] = []
        failed_args: list[tuple] = []
        worker.pipeline_finished.connect(lambda: finished.append("finished"))
        worker.pipeline_failed.connect(lambda *a: failed_args.append(a))

        with patch(
            "src.pipeline.phases.run_optimization_pipeline",
            side_effect=RuntimeError("boom"),
        ):
            worker.run()

        assert not finished, "pipeline_finished must not fire on exception"
        assert len(failed_args) == 1
        exc_type, message, _tb = failed_args[0]
        assert exc_type == "RuntimeError"
        assert "boom" in message

    def test_cancel_check_cleared_after_successful_run(self):
        """The finally block must clear the cancel check even on success."""
        worker = PipelineWorker()
        _state.set_cancel_check(None)
        with patch("src.pipeline.phases.run_optimization_pipeline"):
            worker.run()
        assert _state.is_cancelled() is False

    def test_cancel_check_cleared_after_exception(self):
        """The finally block must clear the cancel check even when run raises."""
        worker = PipelineWorker()
        with patch(
            "src.pipeline.phases.run_optimization_pipeline",
            side_effect=ValueError("err"),
        ):
            worker.run()
        assert _state.is_cancelled() is False
