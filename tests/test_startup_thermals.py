"""Tests for src.pipeline.startup_thermals.run_startup_thermal_scan."""
from unittest.mock import patch, MagicMock, call

from src.pipeline.startup_thermals import run_startup_thermal_scan, _SENSOR_RETRIES


_SAFE_RESULT = {
    "safe": True,
    "cpu_temp": 42.0,
    "gpu_temp": 58.0,
    "message": "Idle temps look good (CPU: 42°C, GPU: 58°C) — safe to benchmark.",
}
_NO_DATA_RESULT = {
    "safe": True,
    "cpu_temp": None,
    "gpu_temp": None,
    "message": "No thermal data available — proceeding without pre-check.",
}


def _mock_lhm(available: bool) -> MagicMock:
    """Return a mocked LHMSidecar instance with start() returning ``available``."""
    inst = MagicMock()
    inst.start.return_value = available
    return inst


class TestRunStartupThermalScan:

    # ── LHM unavailable ──────────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_lhm_unavailable_returns_false(self, MockLHM, mock_fetch):
        """LHM start fails → lhm_available=False, fetch_snapshot never called."""
        MockLHM.return_value = _mock_lhm(False)

        _, available = run_startup_thermal_scan()

        assert available is False
        mock_fetch.assert_not_called()

    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_lhm_unavailable_prints_skip_message(self, MockLHM, mock_fetch, capsys):
        """LHM unavailable → 'unavailable' appears in output."""
        MockLHM.return_value = _mock_lhm(False)

        run_startup_thermal_scan()

        assert "unavailable" in capsys.readouterr().out.lower()

    # ── LHM available, empty snapshot ────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_NO_DATA_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot", return_value={})
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_empty_snapshot_returns_true(self, MockLHM, _fetch, _check):
        """Empty temps → lhm_available True (LHM is up), no crash."""
        MockLHM.return_value = _mock_lhm(True)

        _, available = run_startup_thermal_scan()

        assert available is True

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_NO_DATA_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot", return_value={})
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_empty_snapshot_prints_no_data_message(self, MockLHM, _fetch, _check, capsys):
        """Empty temps → 'skipped' in output."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()

        assert "skipped" in capsys.readouterr().out.lower()

    # ── All temps OK ─────────────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_safe_temps_shows_success_and_values(self, MockLHM, _fetch, _check, capsys):
        """Safe temps → success indicator and both values in output."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert any(tok in out for tok in ["\u2713", "OK"])
        assert "42" in out
        assert "58" in out

    # ── CPU above threshold ───────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value={
        "safe": False, "cpu_temp": 78.0, "gpu_temp": 60.0,
        "message": "CPU is already at 78°C at idle — under full load it could exceed 93°C.",
    })
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_cpu_above_threshold_shows_warning(self, MockLHM, _fetch, _check, capsys):
        """CPU >= CPU_IDLE_WARN → warning indicator and CPU value in output."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "78" in out
        assert any(tok in out for tok in ["\u26a0", "WARN"])

    # ── GPU above threshold ───────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value={
        "safe": False, "cpu_temp": None, "gpu_temp": 82.0,
        "message": "GPU is already at 82°C at idle — under full load it could exceed 97°C.",
    })
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_gpu_above_threshold_shows_warning(self, MockLHM, _fetch, _check, capsys):
        """GPU >= GPU_IDLE_WARN → warning indicator and GPU value in output."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "82" in out
        assert any(tok in out for tok in ["\u26a0", "WARN"])

    # ── Both above threshold ──────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value={
        "safe": False, "cpu_temp": 78.0, "gpu_temp": 85.0,
        "message": "CPU is already at 78°C... GPU is already at 85°C...",
    })
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_both_above_threshold_shows_both_values(self, MockLHM, _fetch, _check, capsys):
        """Both CPU and GPU elevated → both values appear in output."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "78" in out
        assert "85" in out

    # ── Only CPU data ─────────────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value={
        "safe": True, "cpu_temp": 55.0, "gpu_temp": None,
        "message": "Idle temps look good (CPU: 55°C) — safe to benchmark.",
    })
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_only_cpu_data_omits_gpu_line(self, MockLHM, _fetch, _check, capsys):
        """No GPU sensor → CPU shown, no GPU line."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "55" in out
        assert "GPU Temp" not in out

    # ── Only GPU data ─────────────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value={
        "safe": True, "cpu_temp": None, "gpu_temp": 60.0,
        "message": "Idle temps look good (GPU: 60°C) — safe to benchmark.",
    })
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_only_gpu_data_omits_cpu_line(self, MockLHM, _fetch, _check, capsys):
        """No CPU sensor → GPU shown, no CPU line."""
        MockLHM.return_value = _mock_lhm(True)

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "60" in out
        assert "CPU Temp" not in out

    # ── Return value structure ────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_returns_lhm_instance_and_true(self, MockLHM, _fetch, _check):
        """Return value is (LHMSidecar instance, True) when temps read successfully."""
        mock_inst = _mock_lhm(True)
        MockLHM.return_value = mock_inst

        lhm, available = run_startup_thermal_scan()

        assert lhm is mock_inst
        assert available is True

    # ── Sensor retry logic ────────────────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.sleep")
    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_retries_until_sensors_populate(self, MockLHM, mock_fetch, _check, mock_sleep):
        """Empty snapshots cause retries; succeeds when sensors finally appear."""
        MockLHM.return_value = _mock_lhm(True)
        # First two calls empty, third has data
        mock_fetch.side_effect = [{}, {}, {"CPU Package": 45.0}]

        run_startup_thermal_scan()

        assert mock_fetch.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("src.pipeline.startup_thermals.sleep")
    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_NO_DATA_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot", return_value={})
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_retries_exhaust_then_no_data(self, MockLHM, _fetch, _check, mock_sleep):
        """All retries return empty → shows 'skipped', fetch called _SENSOR_RETRIES times."""
        MockLHM.return_value = _mock_lhm(True)

        _, available = run_startup_thermal_scan()

        assert _fetch.call_count == _SENSOR_RETRIES
        assert mock_sleep.call_count == _SENSOR_RETRIES - 1
        assert available is True  # LHM is up even if sensors are empty

    @patch("src.pipeline.startup_thermals.sleep")
    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_no_sleep_after_last_retry(self, MockLHM, mock_fetch, _check, mock_sleep):
        """No sleep is inserted after the final retry attempt."""
        MockLHM.return_value = _mock_lhm(True)
        mock_fetch.side_effect = [{}] * _SENSOR_RETRIES + [{"CPU Package": 45.0}]

        run_startup_thermal_scan()

        # sleep called exactly _SENSOR_RETRIES - 1 times (no sleep after last attempt)
        assert mock_sleep.call_count == _SENSOR_RETRIES - 1

    @patch("src.pipeline.startup_thermals.sleep")
    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_no_retry_when_first_snapshot_has_data(self, MockLHM, mock_fetch, _check, mock_sleep):
        """Data on first fetch → no retries, no sleep."""
        MockLHM.return_value = _mock_lhm(True)
        mock_fetch.return_value = {"CPU Package": 45.0}

        run_startup_thermal_scan()

        assert mock_fetch.call_count == 1
        mock_sleep.assert_not_called()

    # ── Progress message during retry ────────────────────────────────────────

    @patch("src.pipeline.startup_thermals.sleep")
    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_progress_message_shown_during_retry(self, MockLHM, mock_fetch, _check, mock_sleep, capsys):
        """When first fetch is empty, 'Waiting for sensor data' appears in output."""
        MockLHM.return_value = _mock_lhm(True)
        mock_fetch.side_effect = [{}, {"CPU Package": 45.0}]

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "Waiting for sensor data" in out

    @patch("src.pipeline.startup_thermals.sleep")
    @patch("src.pipeline.startup_thermals.check_idle_thermals", return_value=_SAFE_RESULT)
    @patch("src.pipeline.startup_thermals.fetch_snapshot")
    @patch("src.pipeline.startup_thermals.LHMSidecar")
    def test_no_progress_message_on_first_success(self, MockLHM, mock_fetch, _check, mock_sleep, capsys):
        """Data on first try → no 'Waiting for sensor data' message."""
        MockLHM.return_value = _mock_lhm(True)
        mock_fetch.return_value = {"CPU Package": 45.0}

        run_startup_thermal_scan()
        out = capsys.readouterr().out

        assert "Waiting for sensor data" not in out
