"""Tests for src/pipeline/phase_bootstrap.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.pipeline.base import PipelineAborted, PipelineContext, PhaseResult
from src.pipeline.phase_bootstrap import BootstrapPhase
from src.utils.errors import LilBroError, RestorePointError


def _make_ctx(**kwargs) -> PipelineContext:
    defaults = dict(lhm=MagicMock(), thermal=MagicMock())
    defaults.update(kwargs)
    return PipelineContext(**defaults)


@pytest.fixture(autouse=True)
def _default_no_session_manifest():
    """BootstrapPhase.run now consults load_manifest() first; default it to None
    so the create-restore-point path runs for the existing tests. The reuse test
    overrides this with its own patch."""
    with patch("src.utils.revert.load_manifest", return_value=None):
        yield


class TestBootstrapPhase:
    def test_happy_path_sets_restore_point_created(self):
        """create_restore_point() succeeds → restore_point_created=True, returns completed."""
        ctx = _make_ctx(restore_point_created=False)
        with patch("src.pipeline.phase_bootstrap.create_restore_point"), \
             patch("src.utils.revert.mark_restore_point_created"), \
             patch("src.pipeline.phase_bootstrap.print_header"), \
             patch("src.pipeline.phase_bootstrap.get_debug_logger"):
            result = BootstrapPhase().run(ctx)
        assert ctx.restore_point_created is True
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
        assert "Restore point created" in result.message

    def test_lil_bro_error_prompt_approved_continues(self):
        """create_restore_point() raises LilBroError, prompt_approval returns True → returns degraded result."""
        ctx = _make_ctx(restore_point_created=False)
        with patch("src.pipeline.phase_bootstrap.create_restore_point", side_effect=LilBroError("test error")), \
             patch("src.pipeline.phase_bootstrap.prompt_approval", return_value=True), \
             patch("src.pipeline.phase_bootstrap.print_header"), \
             patch("src.pipeline.phase_bootstrap.print_error"), \
             patch("src.pipeline.phase_bootstrap.get_debug_logger"):
            result = BootstrapPhase().run(ctx)
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
        assert result.error is not None
        assert "failed — user chose to continue" in result.message

    def test_lil_bro_error_prompt_denied_aborts(self):
        """create_restore_point() raises LilBroError, prompt_approval returns False → raises PipelineAborted."""
        ctx = _make_ctx(restore_point_created=False)
        with patch("src.pipeline.phase_bootstrap.create_restore_point", side_effect=LilBroError("test error")), \
             patch("src.pipeline.phase_bootstrap.prompt_approval", return_value=False), \
             patch("src.pipeline.phase_bootstrap.print_header"), \
             patch("src.pipeline.phase_bootstrap.print_error"), \
             patch("src.pipeline.phase_bootstrap.get_debug_logger"):
            with pytest.raises(PipelineAborted):
                BootstrapPhase().run(ctx)

    def test_restore_point_error_also_caught(self):
        """create_restore_point() raises RestorePointError (LilBroError subclass) → same gate fires."""
        ctx = _make_ctx(restore_point_created=False)
        with patch("src.pipeline.phase_bootstrap.create_restore_point", side_effect=RestorePointError("test restore error")), \
             patch("src.pipeline.phase_bootstrap.prompt_approval", return_value=True), \
             patch("src.pipeline.phase_bootstrap.print_header"), \
             patch("src.pipeline.phase_bootstrap.print_error"), \
             patch("src.pipeline.phase_bootstrap.get_debug_logger"):
            result = BootstrapPhase().run(ctx)
        assert isinstance(result, PhaseResult)
        assert result.status == "completed"
        assert result.error is not None


    def test_skips_creation_when_restore_point_already_exists(self):
        """A card fix earlier this session already created a restore point:
        BootstrapPhase reuses it (no second create_restore_point, so no duplicate
        identically-labelled 'lil_bro' entry in rstrui.exe)."""
        ctx = _make_ctx(restore_point_created=False)
        with patch("src.utils.revert.load_manifest", return_value={"restore_point_created": True}), \
             patch("src.pipeline.phase_bootstrap.create_restore_point") as mock_create, \
             patch("src.pipeline.phase_bootstrap.print_header"), \
             patch("src.pipeline.phase_bootstrap.print_step"), \
             patch("src.pipeline.phase_bootstrap.get_debug_logger"):
            result = BootstrapPhase().run(ctx)
        mock_create.assert_not_called()
        assert ctx.restore_point_created is True
        assert result.status == "completed"
        assert "Reused existing restore point" in result.message
