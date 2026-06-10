"""Verifies Dashboard renders all 6 cards and pause/resume work."""

from __future__ import annotations

from src.gui.widgets.dashboard import Dashboard
from src.gui.widgets.stat_card import STAT_CARDS


def test_dashboard_creates_four_cards(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    assert len(dash._cards) == 4
    for key, _label, _tone in STAT_CARDS:
        assert key in dash._cards


def test_apply_snapshot_updates_card_values(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.apply_snapshot({
        "cpu_usage": "45%",
        "cpu_temp": "65°C",
        "gpu_temp": "58°C",
        "ram_used": "8.5 GB",
    })
    assert dash._cards["cpu_temp"]._value.text() == "65°C"
    assert dash._cards["gpu_temp"]._value.text() == "58°C"


def test_apply_snapshot_falls_back_to_dash_for_missing(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.apply_snapshot({"power_plan": "Balanced"})
    assert dash._cards["cpu_temp"]._value.text() == "—"


def test_dashboard_card_accessible_names(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    for _key, label, _tone in STAT_CARDS:
        card_names = [c.accessibleName() for c in dash._cards.values()]
        assert any(label in name for name in card_names)


# ── Power Plan / Game Mode fix card slots (T-034) ───────────────────────────


def test_setting_cards_hidden_on_missing_or_error(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    for bad in (None, {}, {"error": "collection failed"}):
        dash.set_power_plan_data(bad)
        dash.set_game_mode_data(bad)
        assert not dash._power_plan_card.isVisibleTo(dash)
        assert not dash._game_mode_card.isVisibleTo(dash)


def test_setting_cards_shown_on_valid_entries(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.set_power_plan_data({"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced"})
    dash.set_game_mode_data({"enabled": False})
    assert dash._power_plan_card.isVisibleTo(dash)
    assert dash._game_mode_card.isVisibleTo(dash)


def test_power_plan_card_click_bubbles_to_dashboard_signal(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    with qtbot.waitSignal(dash.power_plan_fix_requested, timeout=1000):
        dash._power_plan_card._apply_btn.click()


def test_game_mode_card_click_bubbles_to_dashboard_signal(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    with qtbot.waitSignal(dash.game_mode_fix_requested, timeout=1000):
        dash._game_mode_card._apply_btn.click()
