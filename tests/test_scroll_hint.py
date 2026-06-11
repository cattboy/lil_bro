"""ScrollHintArrow: visibility from scroll range, pulse lifecycle, click scroll."""

from __future__ import annotations

from PySide6.QtCore import QPropertyAnimation
from PySide6.QtWidgets import QScrollArea, QWidget

from src.gui.widgets.scroll_hint import ScrollHintArrow


def _make_area(qtbot, content_height: int) -> tuple[QScrollArea, ScrollHintArrow]:
    area = QScrollArea()
    area.setWidgetResizable(True)
    inner = QWidget()
    inner.setMinimumHeight(content_height)
    area.setWidget(inner)
    hint = ScrollHintArrow(area)
    area.setFixedSize(300, 200)
    qtbot.addWidget(area)
    area.show()
    qtbot.waitUntil(area.isVisible, timeout=2000)
    qtbot.wait(20)  # let the scrollbar range settle
    return area, hint


def test_hidden_when_content_fits(qtbot):
    area, hint = _make_area(qtbot, content_height=100)
    assert area.verticalScrollBar().maximum() == 0
    assert not hint.isVisibleTo(area)
    assert hint._pulse.state() != QPropertyAnimation.State.Running


def test_visible_and_pulsing_when_overflowing(qtbot):
    area, hint = _make_area(qtbot, content_height=1000)
    assert area.verticalScrollBar().maximum() > 0
    assert hint.isVisibleTo(area)
    assert hint._pulse.state() == QPropertyAnimation.State.Running


def test_first_scroll_stops_pulse_but_keeps_arrow(qtbot):
    area, hint = _make_area(qtbot, content_height=1000)
    vbar = area.verticalScrollBar()
    vbar.setValue(10)  # a small user scroll — not to the bottom
    assert hint._interacted
    assert hint._pulse.state() != QPropertyAnimation.State.Running
    # Still a click affordance while content remains below
    assert hint.isVisibleTo(area)


def test_hides_at_bottom_reappears_above_without_pulse(qtbot):
    area, hint = _make_area(qtbot, content_height=1000)
    vbar = area.verticalScrollBar()
    vbar.setValue(vbar.maximum())
    assert not hint.isVisibleTo(area)
    vbar.setValue(0)
    assert hint.isVisibleTo(area)
    # The pulse stays off after the first interaction
    assert hint._pulse.state() != QPropertyAnimation.State.Running


def test_click_scrolls_down_a_page(qtbot):
    area, hint = _make_area(qtbot, content_height=2000)
    vbar = area.verticalScrollBar()
    assert vbar.value() == 0
    target = min(vbar.pageStep(), vbar.maximum())
    hint.click()
    qtbot.waitUntil(lambda: vbar.value() == target, timeout=2000)
