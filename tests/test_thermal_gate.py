"""Tests for src.pipeline.thermal_gate.thermal_safety_gate."""
from unittest.mock import patch
from src.pipeline.thermal_gate import thermal_safety_gate


class TestThermalSafetyGate:
    def test_no_lhm_returns_false(self):
        """No LHM available -- should not skip."""
        assert thermal_safety_gate(lhm_available=False) is False

    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_safe_temps_returns_false(self, mock_check, mock_fetch):
        """Safe temps -- proceed."""
        mock_fetch.return_value = {"cpu": 45.0}
        mock_check.return_value = {"safe": True, "message": "Temps look good."}
        assert thermal_safety_gate(lhm_available=True) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=True)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_elevated_user_approves_returns_false(self, mock_check, mock_fetch, mock_approval):
        """Elevated temps but user approves -- proceed."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        assert thermal_safety_gate(lhm_available=True) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_elevated_user_declines_returns_true(self, mock_check, mock_fetch, mock_approval):
        """Elevated temps and user declines -- skip."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        assert thermal_safety_gate(lhm_available=True) is True

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_custom_skip_message(self, mock_check, mock_fetch, mock_approval, capsys):
        """Custom skip message is printed."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "hot"}
        thermal_safety_gate(lhm_available=True, skip_message="Custom skip msg")
        out = capsys.readouterr().out
        assert "Custom skip msg" in out

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    def test_custom_approval_prompt(self, mock_check, mock_fetch, mock_approval):
        """Custom approval prompt is passed to prompt_approval."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "hot"}
        thermal_safety_gate(lhm_available=True, approval_prompt="Custom prompt?")
        mock_approval.assert_called_once_with("Custom prompt?")
