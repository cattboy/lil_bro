"""Tests for the GameModeCard dashboard widget.

Offscreen Qt (conftest.py) + qtbot. WARNING findings come from the real
analyze_game_mode so these tests can't drift from the analyzer's output
shape; expected copy is read from FALLBACK_PROPOSALS (never hardcoded).
"""
from __future__ import annotations

from src.agent_tools.game_mode import analyze_game_mode
from src.gui.widgets.game_mode_card import _APPLIED_TEXT, GameModeCard
from src.llm.action_proposer import FALLBACK_PROPOSALS

_DISABLED = {"GameMode": {"enabled": False}}
_ENABLED = {"GameMode": {"enabled": True}}


def test_apply_button_emits_apply_requested(qtbot):
    card = GameModeCard()
    qtbot.addWidget(card)
    card.set_findings(analyze_game_mode(_DISABLED))
    with qtbot.waitSignal(card.apply_requested, timeout=1000):
        card._apply_btn.click()


def test_warning_shows_message_button_and_medium_sev(qtbot):
    card = GameModeCard()
    qtbot.addWidget(card)
    finding = analyze_game_mode(_DISABLED)
    card.set_findings(finding)
    assert card._status_lbl.text() == finding["message"]
    assert card._status_lbl.toolTip() == FALLBACK_PROPOSALS["game_mode"]["explanation"]
    assert card._status_lbl.property("sev") == "medium"
    assert card._apply_btn.isVisibleTo(card)


def test_ok_shows_checkmark_and_hides_button(qtbot):
    card = GameModeCard()
    qtbot.addWidget(card)
    finding = analyze_game_mode(_ENABLED)
    card.set_findings(finding)
    assert card._status_lbl.text() == f"✓ {finding['message']}"
    assert card._status_lbl.property("sev") == "low"
    assert not card._apply_btn.isVisibleTo(card)


def test_bare_ok_renders_optimistic_applied_text(qtbot):
    """{"status": "OK"} without a message is the post-fix optimistic state
    (StartupCoordinator._on_setting_fix_result)."""
    card = GameModeCard()
    qtbot.addWidget(card)
    card.set_findings(analyze_game_mode(_DISABLED))  # button shown first
    card.set_findings({"status": "OK"})
    assert card._status_lbl.text() == _APPLIED_TEXT
    assert not card._apply_btn.isVisibleTo(card)
