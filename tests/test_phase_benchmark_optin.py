"""Tests for src.pipeline.phase_benchmark_optin.BenchmarkOptInPhase."""
from unittest.mock import MagicMock, patch

from src.pipeline.base import PipelineContext, PhaseResult
from src.pipeline.phase_benchmark_optin import BenchmarkOptInPhase


def _make_ctx(**kwargs) -> PipelineContext:
    defaults = dict(lhm=MagicMock(), thermal=MagicMock())
    defaults.update(kwargs)
    return PipelineContext(**defaults)


class TestBenchmarkOptInPhase:
    def test_skips_when_lhm_unavailable(self):
        """LHM unavailable must set run_benchmarks=False and return skipped."""
        ctx = _make_ctx(lhm_available=False)
        result = BenchmarkOptInPhase().run(ctx)
        assert ctx.run_benchmarks is False
        assert isinstance(result, PhaseResult)
        assert result.status == "skipped"

    @patch("src.pipeline.phase_benchmark_optin.prompt_benchmark_optin", return_value=True)
    def test_optin_sets_run_benchmarks_true(self, _mock):
        """User opt-in must set run_benchmarks=True and return completed."""
        ctx = _make_ctx(lhm_available=True)
        result = BenchmarkOptInPhase().run(ctx)
        assert ctx.run_benchmarks is True
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"

    @patch("src.pipeline.phase_benchmark_optin.prompt_benchmark_optin", return_value=False)
    def test_optout_sets_run_benchmarks_false(self, _mock):
        """User opt-out must set run_benchmarks=False and return completed."""
        ctx = _make_ctx(lhm_available=True)
        result = BenchmarkOptInPhase().run(ctx)
        assert ctx.run_benchmarks is False
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
