"""Verifies ThermalChart sample buffering, threshold rendering, and offline overlay."""

from __future__ import annotations

from src.gui.widgets.thermal_chart import ThermalChart, _CRIT_C, _WARN_C


def test_chart_starts_offline(qtbot):
    chart = ThermalChart()
    qtbot.addWidget(chart)
    assert chart._offline is True


def test_append_sample_clears_offline(qtbot):
    chart = ThermalChart()
    qtbot.addWidget(chart)
    chart.append_sample(60.0, 55.0)
    assert chart._offline is False
    assert chart.latest_cpu == 60.0
    assert chart.latest_gpu == 55.0


def test_append_sample_skips_none(qtbot):
    chart = ThermalChart()
    qtbot.addWidget(chart)
    chart.append_sample(None, 50.0)
    assert chart.latest_cpu is None
    assert chart.latest_gpu == 50.0


def test_set_offline_renders_status(qtbot):
    chart = ThermalChart()
    qtbot.addWidget(chart)
    chart.append_sample(60.0, 55.0)
    chart.set_offline("Thermal monitor offline")
    assert chart._offline is True
    assert "offline" in chart._status_text.lower()


def test_thresholds_match_design_plan():
    assert _WARN_C == 75.0
    assert _CRIT_C == 85.0


def test_clear_samples_resets_state(qtbot):
    chart = ThermalChart()
    qtbot.addWidget(chart)
    for c, g in [(60, 55), (62, 56), (61, 57)]:
        chart.append_sample(c, g)
    chart.clear_samples()
    assert chart.latest_cpu is None
    assert chart.latest_gpu is None


def test_paint_event_does_not_crash(qtbot):
    chart = ThermalChart()
    qtbot.addWidget(chart)
    chart.resize(200, 140)
    chart.append_sample(60.0, 55.0)
    chart.append_sample(70.0, 78.0)
    chart.append_sample(82.0, 90.0)
    chart.show()
    qtbot.waitExposed(chart)
    # If paintEvent throws, the show()/expose path raises here.
