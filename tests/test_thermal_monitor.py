import json
import pytest
from unittest.mock import patch, MagicMock

from src.benchmarks.thermal_monitor import (
    ThermalMonitor,
    _parse_temps_from_lhm,
    _fetch_temps,
)


# ── LHM JSON parsing tests ──────────────────────────────────────────────────

def _make_lhm_tree(cpu_temps: dict[str, str], gpu_temps: dict[str, str] | None = None):
    """Build a minimal LHM-style JSON tree with temperature sensors."""
    cpu_children = [{"Text": k, "Value": v} for k, v in cpu_temps.items()]
    gpu_children = [{"Text": k, "Value": v} for k, v in (gpu_temps or {}).items()]

    tree = {
        "Text": "Sensor",
        "Children": [
            {
                "Text": "Intel Core i7",
                "Children": [
                    {"Text": "Temperatures", "Children": cpu_children},
                ],
            },
        ],
    }
    if gpu_temps:
        tree["Children"].append({
            "Text": "NVIDIA RTX 3080",
            "Children": [
                {"Text": "Temperatures", "Children": gpu_children},
            ],
        })
    return tree


def test_parse_temps_basic():
    tree = _make_lhm_tree(
        {"CPU Package": "72.3 °C", "CPU Core #1": "71.0 °C"},
        {"GPU Core": "65.5 °C"},
    )
    temps = _parse_temps_from_lhm(tree)
    assert temps["Intel Core i7 > CPU Package"] == pytest.approx(72.3)
    assert temps["Intel Core i7 > CPU Core #1"] == pytest.approx(71.0)
    assert temps["NVIDIA RTX 3080 > GPU Core"] == pytest.approx(65.5)


def test_parse_temps_inactive_sensor():
    """Sensors showing '- °C' (inactive) should be skipped."""
    tree = _make_lhm_tree({"CPU Package": "72.0 °C", "CPU Core #2": "- °C"})
    temps = _parse_temps_from_lhm(tree)
    assert "Intel Core i7 > CPU Package" in temps
    assert "Intel Core i7 > CPU Core #2" not in temps


def test_parse_temps_empty_tree():
    assert _parse_temps_from_lhm({}) == {}
    assert _parse_temps_from_lhm({"Children": []}) == {}


def test_parse_temps_comma_decimal():
    """Some locales use comma as decimal separator."""
    tree = _make_lhm_tree({"CPU Package": "72,5 °C"})
    temps = _parse_temps_from_lhm(tree)
    assert temps["Intel Core i7 > CPU Package"] == pytest.approx(72.5)


# ── _fetch_temps tests ───────────────────────────────────────────────────────

@patch("src.benchmarks.thermal_monitor.urllib.request.urlopen")
def test_fetch_temps_success(mock_urlopen):
    tree = _make_lhm_tree({"CPU Package": "80.0 °C"})
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(tree).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    temps = _fetch_temps()
    assert "Intel Core i7 > CPU Package" in temps


@patch("src.benchmarks.thermal_monitor.urllib.request.urlopen", side_effect=Exception("fail"))
def test_fetch_temps_failure(mock_urlopen):
    assert _fetch_temps() == {}


# ── ThermalMonitor integration tests ─────────────────────────────────────────

@patch("src.benchmarks.thermal_monitor._fetch_temps")
def test_monitor_captures_peak(mock_fetch):
    """Monitor should track the highest value seen across multiple samples."""
    mock_fetch.side_effect = [
        {"CPU Package": 70.0, "GPU Core": 60.0},
        {"CPU Package": 85.0, "GPU Core": 65.0},
        {"CPU Package": 75.0, "GPU Core": 72.0},  # GPU peak here
    ]

    monitor = ThermalMonitor(poll_interval=0.01)
    monitor.start()

    import time
    time.sleep(0.1)  # Let a few polls run
    monitor.stop()

    peaks = monitor.get_peak_temps()
    assert peaks.get("CPU Package", 0) >= 85.0
    assert peaks.get("GPU Core", 0) >= 72.0


@patch("src.benchmarks.thermal_monitor._fetch_temps", return_value={})
def test_monitor_no_data(mock_fetch):
    """Monitor should return empty dict if LHM returned no temps."""
    monitor = ThermalMonitor(poll_interval=0.01)
    monitor.start()

    import time
    time.sleep(0.05)
    monitor.stop()

    assert monitor.get_peak_temps() == {}
    assert monitor.sample_count == 0


def test_monitor_get_cpu_peak():
    monitor = ThermalMonitor()
    monitor._peak_temps = {
        "Intel Core i7 > CPU Package": 88.0,
        "Intel Core i7 > CPU Core #1": 85.0,
        "NVIDIA RTX 3080 > GPU Core": 72.0,
    }
    assert monitor.get_cpu_peak() == 88.0


def test_monitor_get_gpu_peak():
    monitor = ThermalMonitor()
    monitor._peak_temps = {
        "Intel Core i7 > CPU Package": 88.0,
        "NVIDIA RTX 3080 > GPU Core": 72.0,
    }
    assert monitor.get_gpu_peak() == 72.0


def test_monitor_get_cpu_peak_none():
    monitor = ThermalMonitor()
    monitor._peak_temps = {"NVIDIA RTX 3080 > GPU Core": 72.0}
    assert monitor.get_cpu_peak() is None


def test_monitor_get_gpu_peak_none():
    monitor = ThermalMonitor()
    monitor._peak_temps = {"Intel Core i7 > CPU Package": 88.0}
    assert monitor.get_gpu_peak() is None


def test_monitor_start_stop_idempotent():
    """Starting twice shouldn't create two threads; stopping twice shouldn't crash."""
    monitor = ThermalMonitor(poll_interval=0.01)
    monitor.start()
    monitor.start()  # should be a no-op
    monitor.stop()
    monitor.stop()  # should not raise
