"""Tests for src/pipeline/base.py — PipelineContext, PhaseResult, PipelineAborted."""

import pytest
from unittest.mock import MagicMock


class TestPipelineAborted:

    def test_is_exception(self):
        from src.pipeline.base import PipelineAborted
        assert issubclass(PipelineAborted, Exception)

    def test_can_raise_and_catch(self):
        from src.pipeline.base import PipelineAborted
        with pytest.raises(PipelineAborted):
            raise PipelineAborted("test reason")

    def test_message_preserved(self):
        from src.pipeline.base import PipelineAborted
        exc = PipelineAborted("restore declined")
        assert "restore declined" in str(exc)


class TestPhaseResult:

    def test_completed_status(self):
        from src.pipeline.base import PhaseResult
        r = PhaseResult(status="completed")
        assert r.status == "completed"
        assert r.message == ""
        assert r.error is None

    def test_skipped_status(self):
        from src.pipeline.base import PhaseResult
        r = PhaseResult(status="skipped", message="user opted out")
        assert r.status == "skipped"
        assert r.message == "user opted out"

    def test_failed_status_with_error(self):
        from src.pipeline.base import PhaseResult
        r = PhaseResult(status="failed", message="oops", error="traceback here")
        assert r.status == "failed"
        assert r.error == "traceback here"


class TestPipelineContext:

    def _make_ctx(self):
        from src.pipeline.base import PipelineContext
        return PipelineContext(lhm=MagicMock(), thermal=MagicMock())

    def test_default_llm_is_none(self):
        ctx = self._make_ctx()
        assert ctx.llm is None

    def test_default_specs_is_empty_dict(self):
        ctx = self._make_ctx()
        assert ctx.specs == {}

    def test_default_fixes_applied_is_zero(self):
        ctx = self._make_ctx()
        assert ctx.fixes_applied == 0

    def test_default_restore_point_created_is_false(self):
        ctx = self._make_ctx()
        assert ctx.restore_point_created is False

    def test_default_approved_proposals_is_empty_list(self):
        ctx = self._make_ctx()
        assert ctx.approved_proposals == []

    def test_default_run_benchmarks_is_none(self):
        ctx = self._make_ctx()
        assert ctx.run_benchmarks is None

    def test_fields_are_mutable(self):
        ctx = self._make_ctx()
        ctx.fixes_applied = 3
        ctx.approved_proposals = [{"finding": "test"}]
        assert ctx.fixes_applied == 3
        assert len(ctx.approved_proposals) == 1
