"""Tests for src.pipeline.phase_apply.ApplyPhase."""
from unittest.mock import MagicMock, patch

from src.pipeline.base import PipelineContext, PhaseResult
from src.pipeline.phase_apply import ApplyPhase


def _make_ctx(**kwargs) -> PipelineContext:
    defaults = dict(lhm=MagicMock(), thermal=MagicMock())
    defaults.update(kwargs)
    return PipelineContext(**defaults)


class TestApplyPhase:
    def test_skip_apply_flag_short_circuits(self):
        """skip_apply=True must return skipped without calling execute_approved_fixes."""
        ctx = _make_ctx(skip_apply=True, approved_proposals=[MagicMock()])
        with patch("src.pipeline.phase_apply.execute_approved_fixes") as mock_exec:
            result = ApplyPhase().run(ctx)
        mock_exec.assert_not_called()
        assert isinstance(result, PhaseResult)
        assert result.status == "skipped"

    def test_no_proposals_short_circuits(self):
        """Empty approved_proposals must return skipped without calling execute_approved_fixes."""
        ctx = _make_ctx(skip_apply=False, approved_proposals=[])
        with patch("src.pipeline.phase_apply.execute_approved_fixes") as mock_exec:
            result = ApplyPhase().run(ctx)
        mock_exec.assert_not_called()
        assert isinstance(result, PhaseResult)
        assert result.status == "skipped"

    def test_applies_and_returns_count(self):
        """When proposals exist and skip_apply is False, execute_approved_fixes is called
        and the count appears in the result message."""
        ctx = _make_ctx(skip_apply=False, approved_proposals=[MagicMock(), MagicMock(), MagicMock()])
        with patch("src.pipeline.phase_apply.execute_approved_fixes", return_value=3):
            result = ApplyPhase().run(ctx)
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
        assert "3" in result.message
