"""Tests for src/pipeline/phases.py -- cancellation and error handling."""
from __future__ import annotations

from unittest.mock import patch, MagicMock

import src.pipeline.phases  # ensure module is loaded before patching
from src.pipeline.phases import run_optimization_pipeline
from src.pipeline.base import PipelineAborted


class TestRunOptimizationPipeline:

    def test_is_cancelled_mid_run_stops_pipeline(self):
        """When is_cancelled returns True between phases, loop exits early."""
        mock_lhm = MagicMock()
        mock_thermal = MagicMock()
        mock_thermal.__enter__.return_value = mock_thermal
        mock_thermal.__exit__.return_value = None

        # Phase run returns a mock result with status "completed"
        mock_phase_result = MagicMock()
        mock_phase_result.status = "completed"
        mock_phase_result.message = "done"

        mock_phase1 = MagicMock()
        mock_phase1.run.return_value = mock_phase_result

        mock_phase2 = MagicMock()
        mock_phase2.run.return_value = mock_phase_result

        mock_phase3 = MagicMock()
        mock_phase3.run.return_value = mock_phase_result

        phases = [mock_phase1, mock_phase2, mock_phase3]

        # After phase 2 runs, is_cancelled returns True, breaking the loop
        is_cancelled_side_effect = [False, False, True]  # Before phase 1, before phase 2, before phase 3

        with patch("src.pipeline.phases.ThermalMonitor", return_value=mock_thermal), \
             patch("src.pipeline.phases._PHASES", phases), \
             patch("src.pipeline._state.is_cancelled", side_effect=is_cancelled_side_effect), \
             patch("src.pipeline.phases.print_header"):
            run_optimization_pipeline(mock_lhm)

        # Phase 1 and 2 should run; phase 3 should not
        assert mock_phase1.run.call_count == 1
        assert mock_phase2.run.call_count == 1
        assert mock_phase3.run.call_count == 0

    def test_pipeline_aborted_is_swallowed(self):
        """When a phase raises PipelineAborted, it is caught and not re-raised."""
        mock_lhm = MagicMock()
        mock_thermal = MagicMock()
        mock_thermal.__enter__.return_value = mock_thermal
        mock_thermal.__exit__.return_value = None

        mock_phase_result = MagicMock()
        mock_phase_result.status = "completed"

        mock_phase1 = MagicMock()
        mock_phase1.run.return_value = mock_phase_result

        # Phase 2 raises PipelineAborted
        mock_phase2 = MagicMock()
        mock_phase2.run.side_effect = PipelineAborted("user cancelled")

        mock_phase3 = MagicMock()
        mock_phase3.run.return_value = mock_phase_result

        phases = [mock_phase1, mock_phase2, mock_phase3]

        with patch("src.pipeline.phases.ThermalMonitor", return_value=mock_thermal), \
             patch("src.pipeline.phases._PHASES", phases), \
             patch("src.pipeline._state.is_cancelled", return_value=False), \
             patch("src.pipeline.phases.print_header"):
            # Should not raise; swallows PipelineAborted
            run_optimization_pipeline(mock_lhm)

        # Phase 1 ran; phase 2 raised but was caught; phase 3 never runs
        assert mock_phase1.run.call_count == 1
        assert mock_phase2.run.call_count == 1
        assert mock_phase3.run.call_count == 0
