"""Tests for the HDRCard widget + Dashboard.set_hdr_data wiring.

Offscreen Qt (conftest.py) + qtbot. Card states come from the real analyze_hdr
so they can't drift. Visibility uses isVisibleTo(parent) / isHidden() rather
than isVisible() — the latter returns False offscreen when the parent isn't
shown (learning qt-isvisible-offscreen-false).
"""

from __future__ import annotations

from src.agent_tools.hdr import analyze_hdr
from src.gui.widgets.hdr_card import HDRCard
from src.llm.action_proposer import propose_for_check


def _specs(*, capable=True, enabled=True, is_win11=True, auto=False, rtx=None):
    specs: dict = {
        "HDRStatus": {
            "determined": True, "is_win11": is_win11, "auto_hdr_enabled": auto,
            "displays": [{"device": "D1", "is_primary": True,
                          "hdr_capable": capable, "hdr_enabled": enabled}],
        }
    }
    if rtx is not None:
        gpu, on = rtx
        specs["NVIDIA"] = [{"GPU": gpu}]
        specs["NVIDIAProfile"] = {"rtx_hdr_enabled": on}
    return specs


# ── Card widget states ───────────────────────────────────────────────────────


def test_suboptimal_auto_shows_settings_button(qtbot):
    card = HDRCard()
    qtbot.addWidget(card)
    finding = analyze_hdr(_specs(auto=False))
    card.set_hdr_status(finding)
    assert card._action_btn.isVisibleTo(card)
    assert card._action_btn.text() == "Open HDR settings"
    assert card._status_lbl.property("sev") == "medium"
    assert card._status_lbl.text() == finding["message"]  # copy from analyzer, not hardcoded


def test_rtx_recommendation_shows_nvidia_button(qtbot):
    card = HDRCard()
    qtbot.addWidget(card)
    card.set_hdr_status(analyze_hdr(_specs(auto=True, rtx=("NVIDIA GeForce RTX 4070", False))))
    assert card._action_btn.isVisibleTo(card)
    assert card._action_btn.text() == "Open NVIDIA App"


def test_optimal_hides_button_low_sev(qtbot):
    card = HDRCard()
    qtbot.addWidget(card)
    card.set_hdr_status(analyze_hdr(_specs(auto=True)))
    assert not card._action_btn.isVisibleTo(card)
    assert card._status_lbl.property("sev") == "low"


def test_fps_note_appended_for_low_tier_rtx(qtbot):
    card = HDRCard()
    qtbot.addWidget(card)
    card.set_hdr_status(analyze_hdr(_specs(auto=True, rtx=("NVIDIA GeForce RTX 3050", False))))
    assert "FPS" in card._status_lbl.text()


def test_hdr_off_shows_windows_settings_button(qtbot):
    card = HDRCard()
    qtbot.addWidget(card)
    card.set_hdr_status(analyze_hdr(_specs(enabled=False)))
    assert card._action_btn.text() == "Open HDR settings"
    assert card._action_btn.isVisibleTo(card)


# ── Dashboard.set_hdr_data show/hide (rescan regression surface) ─────────────


def test_dashboard_shows_and_hides_hdr_card(qtbot):
    from src.gui.widgets.dashboard import Dashboard

    d = Dashboard()
    qtbot.addWidget(d)
    d.set_hdr_data(_specs(auto=False))  # suboptimal -> visible
    assert not d._hdr_card.isHidden()
    d.set_hdr_data({})  # undetermined -> hidden
    assert d._hdr_card.isHidden()
    d.set_hdr_data(_specs(capable=False))  # no HDR panel -> hidden
    assert d._hdr_card.isHidden()
    d.set_hdr_data(_specs(auto=True))  # optimal -> still shown (positive state)
    assert not d._hdr_card.isHidden()


# ── Copy single-sourcing ─────────────────────────────────────────────────────


def test_propose_for_check_hdr_present_and_detection_only():
    p = propose_for_check("hdr")
    assert p is not None
    assert p["finding"] == "hdr"
    assert p["can_auto_fix"] is False  # v1 detection-only
