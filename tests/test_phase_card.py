"""Verifies PhaseCard status transitions and progress slot wiring."""

from __future__ import annotations

import pytest

from src.gui.widgets.phase_card import PhaseCard


def test_phase_card_starts_pending(qtbot):
    card = PhaseCard(1, "Bootstrap")
    qtbot.addWidget(card)
    assert card.status == PhaseCard.STATUS_PENDING


def test_phase_card_set_status_updates_property(qtbot):
    card = PhaseCard(2, "Scan")
    qtbot.addWidget(card)
    card.set_status(PhaseCard.STATUS_ACTIVE)
    assert card.status == PhaseCard.STATUS_ACTIVE


def test_phase_card_done_fills_progress_bar(qtbot):
    card = PhaseCard(5, "Verify")
    qtbot.addWidget(card)
    card.set_status(PhaseCard.STATUS_DONE)
    assert card._progress.value() == 100


def test_phase_card_failed_status(qtbot):
    card = PhaseCard(3, "Configure")
    qtbot.addWidget(card)
    card.set_status(PhaseCard.STATUS_FAILED)
    assert card.status == PhaseCard.STATUS_FAILED


def test_phase_card_rejects_unknown_status(qtbot):
    card = PhaseCard(4, "Baseline")
    qtbot.addWidget(card)
    with pytest.raises(ValueError):
        card.set_status("running")  # not in valid enum


def test_phase_card_progress_signal_clamps_range(qtbot):
    card = PhaseCard(1, "Bootstrap")
    qtbot.addWidget(card)
    card.update_progress(150, "x")
    assert card._progress.value() == 100
    card.update_progress(-5, "y")
    assert card._progress.value() == 0


def test_phase_card_accessible_name(qtbot):
    card = PhaseCard(1, "Bootstrap")
    qtbot.addWidget(card)
    assert "Bootstrap" in card.accessibleName()
