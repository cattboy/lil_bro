"""Tests for the HAGSCard dashboard widget.

Offscreen Qt (conftest.py) + qtbot. WARNING findings come from the real
analyze_hags so these tests can't drift from the analyzer's output shape;
expected copy is read from FALLBACK_PROPOSALS (never hardcoded).
"""
from __future__ import annotations

from src.agent_tools.hags import analyze_hags
from src.gui.widgets.hags_card import _APPLIED_TEXT, HAGSCard
from src.llm.action_proposer import FALLBACK_PROPOSALS

_DISABLED = {"HAGS": {"enabled": False, "supported": True}}
_ENABLED = {"HAGS": {"enabled": True, "supported": True}}


def test_apply_button_emits_apply_requested(qtbot):
    card = HAGSCard()
    qtbot.addWidget(card)
    card.set_findings(analyze_hags(_DISABLED))
    with qtbot.waitSignal(card.apply_requested, timeout=1000):
        card._apply_btn.click()


def test_warning_shows_message_button_and_medium_sev(qtbot):
    card = HAGSCard()
    qtbot.addWidget(card)
    finding = analyze_hags(_DISABLED)
    card.set_findings(finding)
    assert card._status_lbl.text() == finding["message"]
    assert card._status_lbl.toolTip() == FALLBACK_PROPOSALS["hags"]["explanation"]
    assert card._status_lbl.property("sev") == "medium"
    assert card._apply_btn.isVisibleTo(card)


def test_ok_shows_checkmark_and_hides_button(qtbot):
    card = HAGSCard()
    qtbot.addWidget(card)
    finding = analyze_hags(_ENABLED)
    card.set_findings(finding)
    assert card._status_lbl.text() == f"✓ {finding['message']}"
    assert card._status_lbl.property("sev") == "low"
    assert not card._apply_btn.isVisibleTo(card)


def test_bare_ok_renders_optimistic_applied_text(qtbot):
    """{"status": "OK"} without a message is the post-fix optimistic state
    (StartupCoordinator._on_setting_fix_result); the reboot note rides along."""
    card = HAGSCard()
    qtbot.addWidget(card)
    card.set_findings(analyze_hags(_DISABLED))  # button shown first
    card.set_findings({"status": "OK"})
    assert card._status_lbl.text() == _APPLIED_TEXT
    assert not card._apply_btn.isVisibleTo(card)
