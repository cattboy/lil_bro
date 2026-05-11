"""Verifies MousePollingWidget Hz computation, Done button, retry, and idle path."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QTest

from src.gui.widgets.mouse_polling_widget import MousePollingWidget


def _send_move(widget, x, y):
    event = QMouseEvent(
        QMouseEvent.Type.MouseMove,
        QPoint(x, y),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    widget.mouseMoveEvent(event)


def test_no_input_shows_warning(qtbot):
    widget = MousePollingWidget()
    qtbot.addWidget(widget)
    widget._finish()
    assert "no input" in widget._hz_label.text().lower()


def test_move_events_increment_sample_count(qtbot):
    widget = MousePollingWidget()
    qtbot.addWidget(widget)
    for x in range(20):
        _send_move(widget, x, 5)
    assert widget.sample_count == 20


def test_repeat_position_is_ignored(qtbot):
    widget = MousePollingWidget()
    qtbot.addWidget(widget)
    _send_move(widget, 10, 10)
    _send_move(widget, 10, 10)  # same → no count
    _send_move(widget, 11, 10)
    assert widget.sample_count == 2


def test_done_button_emits_measurement_complete(qtbot):
    widget = MousePollingWidget()
    qtbot.addWidget(widget)
    for x in range(50):
        _send_move(widget, x, 0)
        QTest.qWait(2)  # spread events across real elapsed time
    with qtbot.waitSignal(widget.measurement_complete, timeout=1000) as blocker:
        widget.done_btn.click()
    hz = blocker.args[0]
    assert hz > 0


def test_retry_resets_sampling(qtbot):
    widget = MousePollingWidget()
    qtbot.addWidget(widget)
    for x in range(5):
        _send_move(widget, x, 0)
    widget.retry_btn.click()
    assert widget.sample_count == 0
    assert widget._best_hz == 0


def test_widget_has_done_and_retry_buttons(qtbot):
    widget = MousePollingWidget()
    qtbot.addWidget(widget)
    assert widget.done_btn.objectName() == "primary"
    assert widget.retry_btn.text() == "Retry"
