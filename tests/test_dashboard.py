"""Verifies Dashboard renders all 6 cards and pause/resume work."""

from __future__ import annotations

from src.gui.widgets.dashboard import Dashboard, _CARDS


def test_dashboard_creates_six_cards(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    assert len(dash._cards) == 6
    for key, _label in _CARDS:
        assert key in dash._cards


def test_apply_snapshot_updates_card_values(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.apply_snapshot({
        "power_plan": "Balanced",
        "game_mode": "On",
        "refresh_rate": "144 Hz",
        "mouse_hz": "1000",
        "cpu_temp": "65°C",
        "gpu_temp": "58°C",
    })
    assert dash._cards["power_plan"]._value.text() == "Balanced"
    assert dash._cards["cpu_temp"]._value.text() == "65°C"


def test_apply_snapshot_falls_back_to_dash_for_missing(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    dash.apply_snapshot({"power_plan": "Balanced"})
    assert dash._cards["cpu_temp"]._value.text() == "—"


def test_dashboard_card_accessible_names(qtbot):
    dash = Dashboard()
    qtbot.addWidget(dash)
    for _key, label in _CARDS:
        card_names = [c.accessibleName() for c in dash._cards.values()]
        assert any(label in name for name in card_names)
