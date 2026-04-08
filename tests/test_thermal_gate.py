"""Tests for src.pipeline.thermal_gate — thermal_safety_gate and run_thermal_guard."""
from unittest.mock import MagicMock, patch
from src.pipeline.thermal_gate import thermal_safety_gate, run_thermal_guard


def _make_ctx(**kwargs):
    ctx = MagicMock()
    ctx.lhm_available = kwargs.get("lhm_available", True)
    return ctx


class TestRunThermalGuard:
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=True)
    def test_returns_true_when_no_protection(self, mock_require):
        """require_thermal_protection=True short-circuits and returns True."""
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is True
        mock_require.assert_called_once_with("TestPhase", ctx)

    @patch("src.pipeline.thermal_gate.thermal_safety_gate", return_value=True)
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_returns_true_when_temps_too_hot(self, mock_require, mock_gate):
        """thermal_safety_gate=True (temps high, user declines) returns True."""
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is True

    @patch("src.pipeline.thermal_gate.thermal_safety_gate", return_value=False)
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_returns_false_when_safe(self, mock_require, mock_gate):
        """Both checks pass — benchmark should proceed."""
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is False

    @patch("src.pipeline.thermal_gate.thermal_safety_gate", return_value=False)
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_passes_kwargs_to_safety_gate(self, mock_require, mock_gate):
        """Custom skip_message and approval_prompt are forwarded to thermal_safety_gate."""
        ctx = _make_ctx(lhm_available=True)
        run_thermal_guard(
            "TestPhase", ctx,
            skip_message="Custom skip",
            approval_prompt="Custom prompt?",
        )
        mock_gate.assert_called_once_with(
            True,
            skip_message="Custom skip",
            approval_prompt="Custom prompt?",
        )


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
