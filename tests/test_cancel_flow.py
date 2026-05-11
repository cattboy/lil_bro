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
