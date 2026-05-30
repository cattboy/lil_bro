"""Tests for src.pipeline.phase_config.ConfigPhase error handling."""
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.base import PipelineAborted, PipelineContext, PhaseResult
from src.pipeline.phase_config import ConfigPhase

_MINIMAL_SPECS: dict = {
    "DisplayCapabilities": [],
    "GameMode": {},
    "PowerPlan": {},
    "WMI": {"RAM": []},
    "NVIDIA": [],
    "TempFolders": {},
}


def _make_ctx() -> PipelineContext:
    return PipelineContext(
        lhm=MagicMock(),
        thermal=MagicMock(),
        lhm_available=False,
        specs=_MINIMAL_SPECS,
    )


class TestConfigPhaseErrorHandling:
    @patch("src.pipeline.phase_config.run_approval_flow")
    @patch("src.pipeline.phase_config.propose_actions", return_value=[])
    @patch("src.pipeline.phase_config.check_polling_rate", return_value={"status": "OK"})
    @patch("src.pipeline.phase_config.analyze_display", side_effect=RuntimeError("boom"))
    def test_unexpected_exception_does_not_propagate(
        self, _mock_analyze, _mock_poll, _mock_propose, _mock_approval
    ):
        """An unexpected exception in analysis must be caught — pipeline continues."""
        ctx = _make_ctx()
        phase = ConfigPhase()
        result = phase.run(ctx)  # must not raise
        assert isinstance(result, PhaseResult)
        assert result.status == "failed"
        assert result.error is not None

    @patch("src.pipeline.phase_config.run_approval_flow", side_effect=PipelineAborted)
    @patch("src.pipeline.phase_config.propose_actions", return_value=[])
    @patch("builtins.input", return_value="")
    @patch("src.pipeline.phase_config.check_polling_rate", return_value={"status": "OK"})
    @patch("src.pipeline.phase_config.analyze_display", return_value={"status": "OK", "check": "display", "message": ""})
    @patch("src.pipeline.phase_config.analyze_game_mode", return_value={"status": "OK", "check": "game_mode", "message": ""})
    @patch("src.pipeline.phase_config.analyze_power_plan", return_value={"status": "OK", "check": "power_plan", "message": ""})
    @patch("src.pipeline.phase_config.analyze_xmp", return_value={"status": "OK", "check": "xmp", "message": ""})
    @patch("src.pipeline.phase_config.analyze_rebar", return_value={"status": "OK", "check": "rebar", "message": ""})
    @patch("src.pipeline.phase_config.analyze_temp_folders", return_value={"status": "OK", "check": "temp_folders", "message": ""})
    @patch("src.pipeline.phase_config.analyze_nvidia_profile", return_value={"status": "SKIPPED", "check": "nvidia_profile", "message": ""})
    @patch("src.pipeline.phase_config.analyze_thermals", return_value={"status": "OK", "check": "thermals", "message": ""})
    def test_pipeline_aborted_propagates(self, *_mocks):
        """PipelineAborted (user declined) must propagate out of ConfigPhase."""
        ctx = _make_ctx()
        phase = ConfigPhase()
        with pytest.raises(PipelineAborted):
            phase.run(ctx)


class TestConfigPhaseHappyPath:
    @patch("src.pipeline.phase_config.run_approval_flow")
    @patch("src.pipeline.phase_config.propose_actions", return_value=[{"check": "power_plan", "message": "test"}])
    @patch("src.pipeline.phase_config.check_polling_rate", return_value={"status": "OK"})
    @patch("src.pipeline.phase_config.analyze_display", return_value={"status": "OK", "check": "display", "message": ""})
    @patch("src.pipeline.phase_config.analyze_game_mode", return_value={"status": "WARNING", "check": "game_mode", "message": "not optimized"})
    @patch("src.pipeline.phase_config.analyze_power_plan", return_value={"status": "WARNING", "check": "power_plan", "message": "not optimized"})
    @patch("src.pipeline.phase_config.analyze_xmp", return_value={"status": "OK", "check": "xmp", "message": ""})
    @patch("src.pipeline.phase_config.analyze_rebar", return_value={"status": "OK", "check": "rebar", "message": ""})
    @patch("src.pipeline.phase_config.analyze_temp_folders", return_value={"status": "OK", "check": "temp_folders", "message": ""})
    @patch("src.pipeline.phase_config.analyze_nvidia_profile", return_value={"status": "SKIPPED", "check": "nvidia_profile", "message": ""})
    @patch("src.pipeline.phase_config.extract_hardware_summary", return_value={"cpu": "Intel i9", "gpu": "RTX 4090"})
    def test_happy_path_all_analyzers_return_findings(self, *_mocks):
        """All analyzers return valid dicts → run_approval_flow called once → completed."""
        ctx = _make_ctx()
        phase = ConfigPhase()
        result = phase.run(ctx)
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
        assert "analysis complete" in result.message

    @patch("src.pipeline.phase_config.run_approval_flow")
    @patch("src.pipeline.phase_config.propose_actions", return_value=[])
    @patch("src.pipeline.phase_config.check_polling_rate", return_value={"status": "OK"})
    @patch("src.pipeline.phase_config.analyze_display", return_value={"status": "OK", "check": "display", "message": ""})
    @patch("src.pipeline.phase_config.analyze_game_mode", return_value={"status": "OK", "check": "game_mode", "message": ""})
    @patch("src.pipeline.phase_config.analyze_power_plan", return_value={"status": "OK", "check": "power_plan", "message": ""})
    @patch("src.pipeline.phase_config.analyze_xmp", return_value={"status": "OK", "check": "xmp", "message": ""})
    @patch("src.pipeline.phase_config.analyze_rebar", return_value={"status": "OK", "check": "rebar", "message": ""})
    @patch("src.pipeline.phase_config.analyze_temp_folders", return_value={"status": "OK", "check": "temp_folders", "message": ""})
    @patch("src.pipeline.phase_config.analyze_nvidia_profile", return_value={"status": "SKIPPED", "check": "nvidia_profile", "message": ""})
    @patch("src.pipeline.phase_config.extract_hardware_summary", return_value={"cpu": "Intel i9", "gpu": "RTX 4090"})
    def test_happy_path_no_findings_still_completes(self, *_mocks):
        """All analyzers return OK status → approval flow still called → completed."""
        ctx = _make_ctx()
        phase = ConfigPhase()
        result = phase.run(ctx)
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
        assert "analysis complete" in result.message
