"""Tests for the in-card "Applying…" busy state across the dashboard fix cards.

Offscreen Qt (conftest.py) + qtbot. Covers the shared ``set_apply_busy`` helper,
each card's ``set_applying`` (button + DLSS toggle lock), the profile card's
``set_action_available`` button hide/show, the ``_ClickableLabel`` disabled-click
guard, and the Dashboard routing + button-visibility behaviour (including the
post-fix → revert regression: a reverted profile re-shows its Optimize button).

Key regression guard: ``set_applying`` must touch ONLY the action button, never a
card's status QLabel -- otherwise the busy/reset cue would clobber the "✓ optimal"
status the fix-result handler writes before the thread-finished reset runs.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QPushButton

from src.gui.theme import set_apply_busy
from src.gui.widgets.dashboard import Dashboard
from src.gui.widgets.game_mode_card import GameModeCard
from src.gui.widgets.nvidia_dlss_card import NvidiaDlssCard
from src.gui.widgets.nvidia_profile_card import NvidiaProfileCard
from src.gui.widgets.power_plan_card import PowerPlanCard

_WARNING = {
    "status": "WARNING",
    "current": {"gsync": False},
    "expected": {"gsync": True},
    "message": "G-Sync off",
}


# ── Shared helper ───────────────────────────────────────────────────────────


def test_set_apply_busy_round_trips_label_and_enabled(qtbot):
    btn = QPushButton("Go")
    qtbot.addWidget(btn)
    set_apply_busy(btn, True)
    assert btn.text() == "Applying…"
    assert not btn.isEnabled()
    set_apply_busy(btn, False)
    assert btn.text() == "Go"
    assert btn.isEnabled()


# ── NvidiaProfileCard ───────────────────────────────────────────────────────


def test_profile_set_applying_locks_and_restores_button(qtbot):
    card = NvidiaProfileCard("nvidia_profile", "NVIDIA Driver Profile", "Optimize")
    qtbot.addWidget(card)
    card.set_applying(True)
    assert not card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Applying…"
    card.set_applying(False)
    assert card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Optimize"


def test_profile_set_applying_never_touches_status_label(qtbot):
    """Regression: the busy cue is button-only. If set_applying wrote the status
    label, a successful fix's '✓ optimal' (set by the result handler before the
    thread-finished reset) would be clobbered."""
    card = NvidiaProfileCard("nvidia_profile", "NVIDIA Driver Profile", "Optimize")
    qtbot.addWidget(card)
    card.set_gpu("RTX 5090", "Optimize: G-Sync etc.")
    before = card._status_lbl.text()
    card.set_applying(True)
    assert card._status_lbl.text() == before
    card.set_applying(False)
    assert card._status_lbl.text() == before


def test_profile_set_action_available_toggles_button_visibility(qtbot):
    card = NvidiaProfileCard("nvidia_profile", "NVIDIA Driver Profile", "Optimize")
    qtbot.addWidget(card)
    card.set_action_available(False)
    assert not card._apply_btn.isVisibleTo(card)
    card.set_action_available(True)
    assert card._apply_btn.isVisibleTo(card)


# ── NvidiaDlssCard ──────────────────────────────────────────────────────────


def test_dlss_set_applying_locks_button_and_toggle(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_applying(True)
    assert not card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Applying…"
    assert not card._toggle.isEnabled()
    assert not card._quality_lbl.isEnabled()
    assert not card._fps_lbl.isEnabled()
    card.set_applying(False)
    assert card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Apply Preset"
    assert card._toggle.isEnabled()
    assert card._quality_lbl.isEnabled()
    assert card._fps_lbl.isEnabled()


def test_dlss_set_applying_never_touches_status_label(qtbot):
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_gpu("RTX 5090", "Recommended: DLSS Preset L")
    before = card._status_lbl.text()
    card.set_applying(True)
    card.set_applying(False)
    assert card._status_lbl.text() == before


def test_dlss_disabled_label_click_is_suppressed(qtbot):
    """_ClickableLabel must honour setEnabled(False) so a mid-apply click can't
    flip Quality/FPS while set_applying has the control locked."""
    card = NvidiaDlssCard("DLSS Preset", "Apply Preset")
    qtbot.addWidget(card)
    card.set_applying(True)  # disables the toggle + flanking labels
    ev = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        QPointF(1, 1),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.assertNotEmitted(card._fps_lbl.clicked):
        card._fps_lbl.mousePressEvent(ev)
    assert card._toggle.isChecked() is False


# ── PowerPlanCard / GameModeCard ────────────────────────────────────────────


def test_power_plan_set_applying_locks_and_restores_button(qtbot):
    card = PowerPlanCard()
    qtbot.addWidget(card)
    card._apply_btn.setText("Fix Now")
    card.set_applying(True)
    assert not card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Applying…"
    card.set_applying(False)
    assert card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Fix Now"


def test_game_mode_set_applying_locks_and_restores_button(qtbot):
    card = GameModeCard()
    qtbot.addWidget(card)
    card._apply_btn.setText("Fix Now")
    card.set_applying(True)
    assert not card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Applying…"
    card.set_applying(False)
    assert card._apply_btn.isEnabled()
    assert card._apply_btn.text() == "Fix Now"


# ── Dashboard: button visibility + routing ──────────────────────────────────


def test_dashboard_profile_findings_ok_hides_button(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash._nvidia_gpu_name = "RTX 5090"  # normally set by set_nvidia_data first
    dash._nvidia_last_expected = {}
    card = dash._nvidia_full_card
    card.set_action_available(True)  # start visible
    dash.set_nvidia_profile_findings({"status": "OK"})
    assert not card._apply_btn.isVisibleTo(card)


def test_dashboard_profile_findings_warning_shows_button(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash._nvidia_gpu_name = "RTX 5090"  # normally set by set_nvidia_data first
    dash._nvidia_last_expected = {}
    card = dash._nvidia_full_card
    card.set_action_available(False)  # start hidden
    dash.set_nvidia_profile_findings(_WARNING)
    assert card._apply_btn.isVisibleTo(card)


def test_dashboard_profile_button_reappears_after_revert(qtbot):
    """Regression: after a successful fix the button is hidden (OK); a revert
    re-runs the analysis (WARNING) and must re-show the Optimize button."""
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash._nvidia_gpu_name = "RTX 5090"  # normally set by set_nvidia_data first
    dash._nvidia_last_expected = {}
    card = dash._nvidia_full_card
    dash.set_nvidia_profile_findings({"status": "OK"})      # post-fix
    assert not card._apply_btn.isVisibleTo(card)
    dash.set_nvidia_profile_findings(_WARNING)              # post-revert rescan
    assert card._apply_btn.isVisibleTo(card)


def test_dashboard_set_fix_card_applying_routes_to_nvidia_cards(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.set_fix_card_applying("nvidia_profile", True)
    assert not dash._nvidia_full_card._apply_btn.isEnabled()
    assert dash._nvidia_dlss_card._apply_btn.isEnabled()  # untouched
    dash.set_fix_card_applying("nvidia_dlss_preset", True)
    assert not dash._nvidia_dlss_card._apply_btn.isEnabled()
    dash.set_fix_card_applying("nvidia_profile", False)
    assert dash._nvidia_full_card._apply_btn.isEnabled()


def test_dashboard_set_fix_card_applying_display_routes_by_device(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.set_monitor_data([
        {
            "device": r"\\.\DISPLAY1",
            "current_refresh_hz": 60,
            "max_refresh_hz": 144,
            "at_resolution": "1920x1080",
        },
    ])
    slot = dash._monitor_card_slot
    assert slot.device == r"\\.\DISPLAY1"
    dash.set_fix_card_applying("display", True, r"\\.\DISPLAY1")
    assert not slot._fix_btn.isEnabled()
    dash.set_fix_card_applying("display", False, r"\\.\DISPLAY1")
    assert slot._fix_btn.isEnabled()


def test_dashboard_set_fix_card_applying_unknown_check_is_noop(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    # Must not raise for an unmapped check name or a non-matching device.
    dash.set_fix_card_applying("not_a_real_check", True)
    dash.set_fix_card_applying("display", True, r"\\.\NOSUCH")
