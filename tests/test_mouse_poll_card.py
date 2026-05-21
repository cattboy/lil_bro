"""Smoke tests for MousePollCard — construction and snapshot rendering.

The manual "Test Polling" path spawns a background QThread that blocks
~2s; it is deliberately not exercised here. These tests cover the pure,
synchronous surface: construction defaults and ``apply_snapshot``.
"""

from __future__ import annotations

from src.gui.widgets.mouse_poll_card import MousePollCard


def test_mouse_poll_card_constructs(qtbot):
    card = MousePollCard()
    qtbot.addWidget(card)
    assert card._poll_val.text() == "—"
    assert card._poll_status.text() == "Not measured"


def test_apply_snapshot_renders_hz(qtbot):
    card = MousePollCard()
    qtbot.addWidget(card)
    card.apply_snapshot({"mouse_hz": "1000 Hz"})
    assert card._poll_val.text() == "1000"


def test_apply_snapshot_ignored_after_manual_measurement(qtbot):
    card = MousePollCard()
    qtbot.addWidget(card)
    card._mouse_manually_measured = True
    card.apply_snapshot({"mouse_hz": "500 Hz"})
    # Manual measurement is authoritative — periodic snapshot must not clobber.
    assert card._poll_val.text() == "—"


def test_apply_snapshot_skips_placeholder_values(qtbot):
    card = MousePollCard()
    qtbot.addWidget(card)
    card.apply_snapshot({"mouse_hz": "Not measured"})
    assert card._poll_val.text() == "—"
