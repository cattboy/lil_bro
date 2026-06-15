"""Tests for CapNotifier — the non-modal action-log-cap warning slot (T-016/T-023).

Uses the offscreen Qt platform (set in conftest.py) + the qtbot fixture so a
QApplication exists. CardDialog is patched so no real dialog is shown.
"""

from __future__ import annotations

from unittest.mock import patch

from src.gui.cap_notifier import CapNotifier


def test_cap_notifier_shows_once(qtbot):
    """show_cap_reached builds and shows one non-modal card; the second call is a no-op."""
    notifier = CapNotifier()
    with patch("src.gui.cap_notifier.CardDialog") as MockDialog:
        notifier.show_cap_reached()
        notifier.show_cap_reached()  # once-guard: self._dialog is not None

    assert MockDialog.call_count == 1, "CardDialog must be constructed exactly once"
    dialog = MockDialog.return_value
    dialog.show.assert_called_once()  # non-modal .show(), never .exec()
    dialog.exec.assert_not_called()
    # Surfaced above the main window to compensate for the lost OS alert sound.
    dialog.raise_.assert_called_once()
    dialog.activateWindow.assert_called_once()


def test_cap_notifier_text_mentions_cap(qtbot):
    """The card text tells the user the log is full and to remove the file."""
    notifier = CapNotifier()
    with patch("src.gui.cap_notifier.CardDialog") as MockDialog:
        notifier.show_cap_reached()

    args, kwargs = MockDialog.call_args
    joined = " ".join(str(a) for a in args) + " " + " ".join(str(v) for v in kwargs.values())
    assert "100 MB cap" in joined
    assert "remove the file" in joined.lower()
