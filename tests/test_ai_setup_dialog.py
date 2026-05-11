"""Verifies AISetupDialog progress, cancel, retry, and done semantics."""

from __future__ import annotations

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from src.gui.widgets.ai_setup_dialog import (
    AISetupDialog,
    _format_eta,
    _mb,
)


def test_set_progress_updates_bar_and_size(qtbot):
    dialog = AISetupDialog()
    qtbot.addWidget(dialog)
    total = 4 * 1024 * 1024 * 1024  # 4 GB
    dialog.set_progress(total // 2, total)
    assert dialog._bar.value() == 50
    assert "MB" in dialog._size_label.text()


def test_progress_without_total_shows_downloaded_only(qtbot):
    dialog = AISetupDialog()
    qtbot.addWidget(dialog)
    dialog.set_progress(20 * 1024 * 1024, None)
    assert "MB" in dialog._size_label.text()


def test_cancel_button_emits_signal_and_rejects(qtbot):
    dialog = AISetupDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    with qtbot.waitSignal(dialog.cancel_clicked, timeout=1000):
        dialog.cancel_btn.click()
    assert dialog.result() == QDialog.DialogCode.Rejected
    assert dialog.cancel_requested is True


def test_set_error_reveals_retry_button(qtbot):
    dialog = AISetupDialog()
    qtbot.addWidget(dialog)
    dialog.set_error("network timeout")
    assert dialog.retry_btn.isVisible() is False  # show() not called yet
    dialog.show()
    QTest.qWait(10)
    assert dialog.retry_btn.isVisible() is True
    assert "failed" in dialog._status.text().lower()


def test_retry_emits_signal_and_resets_progress(qtbot):
    dialog = AISetupDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog.set_error("network")
    with qtbot.waitSignal(dialog.retry_clicked, timeout=1000):
        dialog.retry_btn.click()
    assert dialog._bar.value() == 0
    assert dialog.cancel_requested is False


def test_set_done_accepts_dialog_via_close_button(qtbot):
    dialog = AISetupDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWait(10)
    dialog.set_done("AI features enabled. Now we're cooking.")
    assert "cooking" in dialog._status.text().lower()
    dialog.cancel_btn.click()
    QTest.qWait(10)
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_mb_helper():
    assert _mb(1024 * 1024 * 5) == 5


def test_format_eta_seconds_only():
    assert _format_eta(45) == "45s"


def test_format_eta_minutes():
    assert _format_eta(605) == "10m 05s"


def test_format_eta_hours():
    assert _format_eta(3 * 3600 + 30 * 60) == "3h 30m"
