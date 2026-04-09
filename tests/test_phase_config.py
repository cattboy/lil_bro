"""Tests for src.pipeline.phase_config.ConfigPhase error handling."""
from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.base import PipelineAborted, PipelineContext
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
        phase.run(ctx)  # must not raise

    @patch("src.pipeline.phase_config.run_approval_flow", side_effect=PipelineAborted)
    @patch("src.pipeline.phase_config.propose_actions", return_value=[])
    @patch("builtins.input", return_value="")
    @patch("src.pipeline.phase_config.check_polling_rate", return_value={"status": "OK"})
    @patch("src.pipeline.phase_config.analyze_display", return_value={"status": "OK", "check": "display", "message": ""})
    @patch("src.pipeline.phase_config.analyze_game_mode", return_value={"status": "OK", "check": "game_mode", "message": ""})
    @patch("src.pipeline.phase_config.analyze_power_plan", return_value={"status": "OK", "check": "power_plan", "message": ""})
    @patch("src.pipeline.phase_config.analyze_xmp", return_value={"status": "OK", "check": "xmp", "message": ""})
    @patch("src.pipeline.phase_config.analyze_rebar", return_value={"status": "OK", "check": "rebar", "message": ""})
    @patch("src.pipeline.phase_config.analyze_temp_folders", return_value={"status": "OK", "check": "temp", "message": ""})
    @patch("src.pipeline.phase_config.analyze_nvidia_profile", return_value={"status": "SKIPPED", "check": "nvidia", "message": ""})
    @patch("src.pipeline.phase_config.analyze_thermals", return_value={"status": "OK", "check": "thermals", "message": ""})
    def test_pipeline_aborted_propagates(self, *_mocks):
        """PipelineAborted (user declined) must propagate out of ConfigPhase."""
        ctx = _make_ctx()
        phase = ConfigPhase()
        with pytest.raises(PipelineAborted):
            phase.run(ctx)
