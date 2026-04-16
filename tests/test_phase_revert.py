"""Tests for src/pipeline/phase_revert.py."""
from __future__ import annotations

from unittest.mock import patch

import pytest

import src.pipeline.phase_revert  # ensure module is loaded before patching  # noqa: F401
from src.pipeline.phase_revert import run_revert_phase


_REVERTIBLE_MANIFEST = {
    "session_id": "20260414_120000",
    "session_date": "2026-04-14T12:00:00",
    "restore_point_created": True,
    "fixes": [
        {
            "fix": "power_plan",
            "revertible": True,
            "before": {"guid": "aaa", "name": "Balanced"},
            "after": {"guid": "bbb", "name": "High Performance"},
            "applied_at": "2026-04-14T12:01:00",
        },
    ],
}

_NON_REVERTIBLE_MANIFEST = {
    "session_id": "20260414_120000",
    "session_date": "2026-04-14T12:00:00",
    "restore_point_created": True,
    "fixes": [
        {
            "fix": "temp_folders",
            "revertible": False,
            "reason": "Deleted temp files cannot be restored",
            "display": "temp files deleted",
            "applied_at": "2026-04-14T12:01:00",
        },
    ],
}


class TestRunRevertPhase:

    def test_empty_state_prints_no_backup_found(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=None), \
             patch("src.pipeline.phase_revert.print_info") as mock_info:
            run_revert_phase()
        combined = " ".join(str(c) for c in mock_info.call_args_list)
        assert "no session backup found" in combined

    def test_all_non_revertible_prints_nothing_to_revert(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=_NON_REVERTIBLE_MANIFEST), \
             patch("src.pipeline.phase_revert.print_info") as mock_info:
            run_revert_phase()
        combined = " ".join(str(c) for c in mock_info.call_args_list)
        assert "nothing to revert" in combined

    def test_user_declines_no_revert_called(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=_REVERTIBLE_MANIFEST), \
             patch("src.pipeline.phase_revert.prompt_approval", return_value=False), \
             patch("src.pipeline.phase_revert.revert_fix") as mock_revert:
            run_revert_phase()
        mock_revert.assert_not_called()

    def test_all_succeeded_prints_success(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=_REVERTIBLE_MANIFEST), \
             patch("src.pipeline.phase_revert.prompt_approval", return_value=True), \
             patch("src.pipeline.phase_revert.revert_fix", return_value=(True, "")), \
             patch("src.pipeline.phase_revert.print_success") as mock_success:
            run_revert_phase()
        combined = " ".join(str(c) for c in mock_success.call_args_list)
        assert "everything's where you left it" in combined

    def test_fix_fails_user_accepts_restore_point(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=_REVERTIBLE_MANIFEST), \
             patch("src.pipeline.phase_revert.prompt_approval", side_effect=[True, True]), \
             patch("src.pipeline.phase_revert.revert_fix", return_value=(False, "NPI.exe not found")), \
             patch("src.pipeline.phase_revert.trigger_system_restore") as mock_restore:
            run_revert_phase()
        mock_restore.assert_called_once()

    def test_fix_fails_user_declines_restore_point(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=_REVERTIBLE_MANIFEST), \
             patch("src.pipeline.phase_revert.prompt_approval", side_effect=[True, False]), \
             patch("src.pipeline.phase_revert.revert_fix", return_value=(False, "error")), \
             patch("src.pipeline.phase_revert.trigger_system_restore") as mock_restore:
            run_revert_phase()
        mock_restore.assert_not_called()

    def test_user_declines_restore_point_exits_cleanly(self):
        with patch("src.pipeline.phase_revert.load_manifest", return_value=_REVERTIBLE_MANIFEST), \
             patch("src.pipeline.phase_revert.prompt_approval", side_effect=[True, False]), \
             patch("src.pipeline.phase_revert.revert_fix", return_value=(False, "error")):
            run_revert_phase()  # must not raise

