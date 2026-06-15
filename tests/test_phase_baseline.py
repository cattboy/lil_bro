"""Tests for src.pipeline.phase_baseline.BaselineBenchPhase.

Covers the 7 execution branches, including the three new branches added for
v0.2.0.0: run_benchmarks=False skip, cancel_override, and skip_apply.
"""
from unittest.mock import MagicMock, patch

from src.pipeline.base import PipelineContext, PhaseResult
from src.pipeline.phase_baseline import BaselineBenchPhase, _SKIP_RESULT_HOT


def _make_ctx(**kwargs) -> PipelineContext:
    defaults = dict(
        lhm=MagicMock(),
        thermal=MagicMock(),
        lhm_available=True,
        run_benchmarks=None,
        approved_proposals=[],
    )
    defaults.update(kwargs)
    return PipelineContext(**defaults)


class TestBaselineBenchPhaseSkipBranches:
    def test_run_benchmarks_false_skips_immediately(self):
        """run_benchmarks=False must return skipped before BenchmarkRunner is created."""
        ctx = _make_ctx(run_benchmarks=False)
        with patch("src.pipeline.phase_baseline.BenchmarkRunner") as mock_runner_cls:
            result = BaselineBenchPhase().run(ctx)
        mock_runner_cls.assert_not_called()
        assert isinstance(result, PhaseResult)
        assert result.status == "skipped"

    @patch("src.pipeline.phase_baseline.run_thermal_guard", return_value=False)
    def test_no_cinebench_sets_fallback_result(self, _):
        """has_cinebench=False must call run_benchmark fallback and return skipped."""
        mock_runner = MagicMock()
        mock_runner.has_cinebench = False
        mock_runner.run_benchmark.return_value = {"status": "cpu_stress"}
        ctx = _make_ctx()
        with patch("src.pipeline.phase_baseline.BenchmarkRunner", return_value=mock_runner):
            result = BaselineBenchPhase().run(ctx)
        mock_runner.run_benchmark.assert_called_once_with(full_suite=False, lhm_available=True)
        assert ctx.peak_temps == {}
        assert result.status == "skipped"

    @patch("src.pipeline.phase_baseline.BenchmarkRunner")
    def test_thermal_guard_fires_sets_skip_result(self, mock_runner_cls):
        """Thermal guard returning True must set _SKIP_RESULT_HOT and return skipped."""
        ctx = _make_ctx()
        with patch("src.pipeline.phase_baseline.run_thermal_guard", return_value=True):
            result = BaselineBenchPhase().run(ctx)
        assert ctx.baseline_result == _SKIP_RESULT_HOT
        assert ctx.peak_temps == {}
        ctx.thermal.start.assert_not_called()
        assert result.status == "skipped"


class TestBaselineBenchPhaseSuccessPath:
    @patch("src.pipeline.phase_baseline.run_thermal_guard", return_value=False)
    @patch("src.utils.formatting.notify_benchmark_score")
    def test_success_path_emits_score_and_returns_completed(self, mock_notify, _):
        """Successful benchmark must emit notify_benchmark_score and return completed."""
        mock_runner = MagicMock()
        mock_runner.has_cinebench = True
        mock_runner.run_benchmark.return_value = {
            "status": "success",
            "scores": {"single": 1200, "multi": 8000},
        }
        ctx = _make_ctx()
        ctx.thermal.get_peak_temps.return_value = {"cpu": 72.0}
        ctx.thermal.get_cpu_peak.return_value = 72.0
        ctx.thermal.get_gpu_peak.return_value = None
        with patch("src.pipeline.phase_baseline.BenchmarkRunner", return_value=mock_runner):
            result = BaselineBenchPhase().run(ctx)
        ctx.thermal.start.assert_called_once()
        ctx.thermal.stop.assert_called_once()
        mock_notify.assert_called_once_with(
            "baseline",
            {"single": 1200, "multi": 8000},
            72.0,
        )
        assert result.status == "completed"


class TestBaselineBenchPhaseApprovalFlow:
    """Tests the cancel_override / skip_apply branches when benchmark aborts."""

    def _run_with_abort(self, prompt_return: bool, approved_proposals=None):
        mock_runner = MagicMock()
        mock_runner.has_cinebench = True
        mock_runner.run_benchmark.return_value = {"status": "aborted"}
        ctx = _make_ctx(approved_proposals=approved_proposals or [MagicMock()])
        ctx.thermal.get_peak_temps.return_value = {}
        ctx.thermal.get_cpu_peak.return_value = None
        ctx.thermal.get_gpu_peak.return_value = None
        with patch("src.pipeline.phase_baseline.run_thermal_guard", return_value=False), \
             patch("src.pipeline.phase_baseline.BenchmarkRunner", return_value=mock_runner), \
             patch("src.pipeline.phase_baseline.prompt_approval", return_value=prompt_return):
            result = BaselineBenchPhase().run(ctx)
        return ctx, result

    def test_abort_user_approves_sets_cancel_override(self):
        """Aborted benchmark + user approves applying anyway → cancel_override=True."""
        ctx, result = self._run_with_abort(prompt_return=True)
        assert ctx.cancel_override is True
        assert ctx.skip_apply is False
        assert result.status == "completed"

    def test_abort_user_declines_sets_skip_apply(self):
        """Aborted benchmark + user declines applying → skip_apply=True."""
        ctx, result = self._run_with_abort(prompt_return=False)
        assert ctx.skip_apply is True
        assert ctx.cancel_override is False
        assert result.status == "completed"

    def test_abort_no_proposals_skips_prompt(self):
        """Aborted benchmark with no approved proposals must not call prompt_approval."""
        mock_runner = MagicMock()
        mock_runner.has_cinebench = True
        mock_runner.run_benchmark.return_value = {"status": "aborted"}
        ctx = _make_ctx(approved_proposals=[])
        ctx.thermal.get_peak_temps.return_value = {}
        ctx.thermal.get_cpu_peak.return_value = None
        ctx.thermal.get_gpu_peak.return_value = None
        with patch("src.pipeline.phase_baseline.run_thermal_guard", return_value=False), \
             patch("src.pipeline.phase_baseline.BenchmarkRunner", return_value=mock_runner), \
             patch("src.pipeline.phase_baseline.prompt_approval") as mock_prompt:
            BaselineBenchPhase().run(ctx)
        mock_prompt.assert_not_called()

    def test_skipped_status_no_prompt_applies_silently(self):
        """Declined benchmark dialog (status=skipped) must not call prompt_approval."""
        mock_runner = MagicMock()
        mock_runner.has_cinebench = True
        mock_runner.run_benchmark.return_value = {"status": "skipped"}
        ctx = _make_ctx(approved_proposals=[MagicMock()])
        ctx.thermal.get_peak_temps.return_value = {}
        ctx.thermal.get_cpu_peak.return_value = None
        ctx.thermal.get_gpu_peak.return_value = None
        with patch("src.pipeline.phase_baseline.run_thermal_guard", return_value=False), \
             patch("src.pipeline.phase_baseline.BenchmarkRunner", return_value=mock_runner), \
             patch("src.pipeline.phase_baseline.prompt_approval") as mock_prompt:
            result = BaselineBenchPhase().run(ctx)
        mock_prompt.assert_not_called()
        assert ctx.skip_apply is False
        assert ctx.cancel_override is False
        assert result.status == "completed"
