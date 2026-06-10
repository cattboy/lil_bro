"""Tests for the PowerPlanCard dashboard widget.

Offscreen Qt (conftest.py) + qtbot. WARNING findings come from the real
analyze_power_plan so these tests can't drift from the analyzer's output
shape; expected copy is read from FALLBACK_PROPOSALS (never hardcoded).
"""
from __future__ import annotations

from src.agent_tools.power_plan import analyze_power_plan
from src.gui.widgets.power_plan_card import _APPLIED_TEXT, PowerPlanCard
from src.llm.action_proposer import FALLBACK_PROPOSALS

_BALANCED = {"PowerPlan": {"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced"}}
_HIGH_PERF = {"PowerPlan": {"guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "name": "High Performance"}}


def test_apply_button_emits_apply_requested(qtbot):
    card = PowerPlanCard()
    qtbot.addWidget(card)
    card.set_findings(analyze_power_plan(_BALANCED))
    with qtbot.waitSignal(card.apply_requested, timeout=1000):
        card._apply_btn.click()


def test_warning_shows_message_button_and_high_sev(qtbot):
    card = PowerPlanCard()
    qtbot.addWidget(card)
    finding = analyze_power_plan(_BALANCED)
    card.set_findings(finding)
    assert card._status_lbl.text() == finding["message"]
    assert card._status_lbl.toolTip() == FALLBACK_PROPOSALS["power_plan"]["explanation"]
    assert card._status_lbl.property("sev") == "high"
    assert card._apply_btn.isVisibleTo(card)


def test_ok_shows_checkmark_and_hides_button(qtbot):
    card = PowerPlanCard()
    qtbot.addWidget(card)
    finding = analyze_power_plan(_HIGH_PERF)
    card.set_findings(finding)
    assert card._status_lbl.text() == f"✓ {finding['message']}"
    assert card._status_lbl.property("sev") == "low"
    assert not card._apply_btn.isVisibleTo(card)


def test_bare_ok_renders_optimistic_applied_text(qtbot):
    """{"status": "OK"} without a message is the post-fix optimistic state
    (StartupCoordinator._on_setting_fix_result)."""
    card = PowerPlanCard()
    qtbot.addWidget(card)
    card.set_findings(analyze_power_plan(_BALANCED))  # button shown first
    card.set_findings({"status": "OK"})
    assert card._status_lbl.text() == _APPLIED_TEXT
    assert not card._apply_btn.isVisibleTo(card)
