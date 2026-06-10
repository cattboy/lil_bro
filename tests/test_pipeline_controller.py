"""Tests for PipelineController.open_system_restore.

The rest of PipelineController is thin Qt signal-wiring glue exercised through
the GUI; this file pins the one method with real branching logic: the System
Restore launch path wired from the Revert page's 'Open System Restore' button.

CardDialog and the revert helpers are patched at their source modules because
open_system_restore imports them lazily inside the method body, so the name is
resolved from the module at call time.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QDialog

from src.gui.pipeline_controller import PipelineController


def _make_controller() -> PipelineController:
    return PipelineController(
        MagicMock(), MagicMock(), {}, MagicMock(), MagicMock()
    )


_MANIFEST_WITH_RP = {
    "schema_version": 1,
    "session_date": "2026-06-10T08:30:00",
    "restore_point_created": True,
    "fixes": [],
}
_MANIFEST_NO_RP = {
    "schema_version": 1,
    "session_date": "2026-06-10T08:30:00",
    "restore_point_created": False,
    "fixes": [],
}


def _patch(exec_result, manifest, trigger_ok=True):
    """Context managers for CardDialog / load_manifest / trigger_system_restore."""
    card = patch("src.gui.widgets.dialogs.CardDialog")
    load = patch("src.utils.revert.load_manifest", return_value=manifest)
    trig = patch("src.utils.revert.trigger_system_restore", return_value=trigger_ok)
    return card, load, trig, exec_result


class TestOpenSystemRestore:
    def test_accept_launches_with_session_date(self):
        card, load, trig, _ = _patch(QDialog.DialogCode.Accepted, _MANIFEST_WITH_RP)
        with card as CardDialog, load, trig as trigger:
            CardDialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            _make_controller().open_system_restore()
            trigger.assert_called_once_with("2026-06-10")
            # Only the confirm dialog — no error fallback when launch succeeds.
            assert CardDialog.call_count == 1

    def test_cancel_does_not_launch(self):
        card, load, trig, _ = _patch(QDialog.DialogCode.Rejected, _MANIFEST_WITH_RP)
        with card as CardDialog, load, trig as trigger:
            CardDialog.return_value.exec.return_value = QDialog.DialogCode.Rejected
            _make_controller().open_system_restore()
            trigger.assert_not_called()
            assert CardDialog.call_count == 1

    def test_launch_failure_shows_error_dialog(self):
        card, load, trig, _ = _patch(
            QDialog.DialogCode.Accepted, _MANIFEST_WITH_RP, trigger_ok=False
        )
        with card as CardDialog, load, trig as trigger:
            CardDialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            _make_controller().open_system_restore()
            trigger.assert_called_once_with("2026-06-10")
            # confirm dialog + error fallback dialog.
            assert CardDialog.call_count == 2
            assert CardDialog.call_args_list[1].kwargs["tone"] == "error"

    def test_confirm_copy_names_point_when_restore_point_exists(self):
        card, load, trig, _ = _patch(QDialog.DialogCode.Accepted, _MANIFEST_WITH_RP)
        with card as CardDialog, load, trig:
            CardDialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            _make_controller().open_system_restore()
            description = CardDialog.call_args_list[0].args[1]
            assert "lil_bro Pre-Tuning 2026-06-10" in description

    def test_confirm_copy_is_generic_without_restore_point(self):
        card, load, trig, _ = _patch(QDialog.DialogCode.Accepted, _MANIFEST_NO_RP)
        with card as CardDialog, load, trig:
            CardDialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            _make_controller().open_system_restore()
            description = CardDialog.call_args_list[0].args[1]
            assert "didn't create a restore point" in description
            assert "lil_bro Pre-Tuning 2026-06-10" not in description

    def test_no_manifest_still_offers_launch(self):
        card, load, trig, _ = _patch(QDialog.DialogCode.Accepted, None)
        with card as CardDialog, load, trig as trigger:
            CardDialog.return_value.exec.return_value = QDialog.DialogCode.Accepted
            _make_controller().open_system_restore()
            # No session → generic copy, empty session_date passed through.
            trigger.assert_called_once_with("")
