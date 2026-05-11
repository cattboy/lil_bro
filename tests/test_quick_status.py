"""Verifies quick_status_snapshot returns a 6-card dict with safe fallbacks.

Each underlying read is mocked so the test runs on any CI machine
(no real powercfg, registry, or LHM required). Production behavior is
exercised manually on Windows during smoke tests.
"""

from __future__ import annotations

from unittest.mock import patch

from src.agent_tools import quick_status


def test_snapshot_returns_all_six_keys():
    snap = quick_status.quick_status_snapshot(lhm=None)
    expected_keys = {"power_plan", "game_mode", "refresh_rate",
                     "mouse_hz", "cpu_temp", "gpu_temp"}
    assert expected_keys == set(snap.keys())


def test_snapshot_uses_dash_for_missing_lhm():
    snap = quick_status.quick_status_snapshot(lhm=None)
    assert snap["cpu_temp"] == "—"
    assert snap["gpu_temp"] == "—"


def test_snapshot_swallows_subsystem_errors():
    with patch.object(quick_status, "_read_power_plan", side_effect=RuntimeError("boom")):
        snap = quick_status.quick_status_snapshot(lhm=None)
    assert snap["power_plan"] == "—"


def test_snapshot_propagates_lhm_temps():
    class FakeLHM:
        def read_latest(self):
            return 65.0, 58.0

    snap = quick_status.quick_status_snapshot(lhm=FakeLHM())
    assert snap["cpu_temp"] == "65°C"
    assert snap["gpu_temp"] == "58°C"


def test_snapshot_handles_lhm_failure():
    class FakeLHM:
        def read_latest(self):
            raise RuntimeError("LHM offline")

    snap = quick_status.quick_status_snapshot(lhm=FakeLHM())
    assert snap["cpu_temp"] == "—"
    assert snap["gpu_temp"] == "—"


def test_safe_returns_fallback_on_exception():
    def raises():
        raise RuntimeError("nope")
    assert quick_status._safe(raises, "fallback") == "fallback"


def test_safe_returns_value_on_success():
    assert quick_status._safe(lambda: "ok", "fallback") == "ok"


def test_safe_returns_fallback_when_value_falsy():
    assert quick_status._safe(lambda: "", "fallback") == "fallback"
