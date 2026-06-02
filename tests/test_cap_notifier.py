"""Tests for CapNotifier — the non-modal action-log-cap warning slot (T-016).

Uses the offscreen Qt platform (set in conftest.py) + the qtbot fixture so a
QApplication exists. QMessageBox is patched so no real dialog is shown.
"""

from __future__ import annotations

from unittest.mock import patch

from src.gui.cap_notifier import CapNotifier


def test_cap_notifier_shows_once(qtbot):
    """show_cap_reached builds and shows one non-modal box; the second call is a no-op."""
    notifier = CapNotifier()
    with patch("src.gui.cap_notifier.QMessageBox") as MockBox:
        notifier.show_cap_reached()
        notifier.show_cap_reached()  # once-guard: self._box is not None

    assert MockBox.call_count == 1, "QMessageBox must be constructed exactly once"
    box = MockBox.return_value
    box.setIcon.assert_called_once()
    box.show.assert_called_once()  # non-modal .show(), never .exec()
    box.exec.assert_not_called()


def test_cap_notifier_text_mentions_cap(qtbot):
    """The dialog text tells the user the log is full and to remove the file."""
    notifier = CapNotifier()
    with patch("src.gui.cap_notifier.QMessageBox") as MockBox:
        notifier.show_cap_reached()

    text = " ".join(str(c) for c in MockBox.return_value.setText.call_args_list)
    assert "100 MB cap" in text
    assert "remove the file" in text.lower()
