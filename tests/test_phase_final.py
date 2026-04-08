"""Tests for src.pipeline.phase_final.FinalBenchPhase."""
from unittest.mock import MagicMock, patch

from src.pipeline.base import PipelineContext
from src.pipeline.phase_final import FinalBenchPhase


def _make_ctx(**kwargs) -> PipelineContext:
    """Build a minimal PipelineContext for testing."""
    defaults = dict(
        lhm=MagicMock(),
        thermal=MagicMock(),
        lhm_available=True,
        runner=None,
        baseline_result={},
    )
    defaults.update(kwargs)
    return PipelineContext(**defaults)


class TestFinalBenchPhaseRunnerGuard:
    def test_skips_cleanly_when_runner_is_none(self, capsys):
        """Phase 5 must not crash when Phase 3 was skipped (ctx.runner=None)."""
        ctx = _make_ctx(runner=None)
        phase = FinalBenchPhase()
        # Should return without raising AttributeError
        phase.run(ctx)
        captured = capsys.readouterr()
        assert "skipped" in captured.out.lower()

    @patch("src.pipeline.phase_final.run_thermal_guard", return_value=True)
    def test_skips_on_thermal_protection_when_runner_set(self, mock_guard):
        """Phase 5 skips via thermal gate when runner exists but LHM unavailable."""
        mock_runner = MagicMock()
        ctx = _make_ctx(runner=mock_runner, lhm_available=False)
        phase = FinalBenchPhase()
        phase.run(ctx)
        mock_runner.run_benchmark.assert_not_called()

    @patch("src.pipeline.phase_final.run_thermal_guard", return_value=False)
    def test_runs_benchmark_when_runner_set_and_thermals_ok(self, mock_guard):
        """Phase 5 calls run_benchmark when runner exists and thermals are safe."""
        mock_runner = MagicMock()
        mock_runner.run_benchmark.return_value = {"status": "success", "scores": {"single": 100}}
        ctx = _make_ctx(runner=mock_runner, lhm_available=True)
        ctx.thermal = MagicMock()
        phase = FinalBenchPhase()
        phase.run(ctx)
        mock_runner.run_benchmark.assert_called_once()
