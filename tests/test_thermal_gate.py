"""Tests for src.pipeline.thermal_gate — run_thermal_guard."""
from unittest.mock import MagicMock, patch
from src.pipeline.thermal_gate import run_thermal_guard


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

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_returns_true_when_temps_too_hot(self, mock_require, mock_check, mock_fetch, mock_approval):
        """Elevated temps and user declines — returns True (skip)."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is True

    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_returns_false_when_safe(self, mock_require, mock_check, mock_fetch):
        """Safe temps — benchmark should proceed."""
        mock_fetch.return_value = {"cpu": 45.0}
        mock_check.return_value = {"safe": True, "message": "Temps look good."}
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_passes_approval_prompt_to_prompt_approval(self, mock_require, mock_check, mock_fetch, mock_approval):
        """Custom approval_prompt is forwarded to prompt_approval."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "hot"}
        ctx = _make_ctx(lhm_available=True)
        run_thermal_guard("TestPhase", ctx, approval_prompt="Custom prompt?")
        mock_approval.assert_called_once_with("Custom prompt?")

    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_no_lhm_returns_false(self, mock_require):
        """No LHM available — proceed without checking temps."""
        ctx = _make_ctx(lhm_available=False)
        assert run_thermal_guard("TestPhase", ctx) is False

    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_safe_temps_returns_false(self, mock_require, mock_check, mock_fetch):
        """Safe idle temps — proceed."""
        mock_fetch.return_value = {"cpu": 45.0}
        mock_check.return_value = {"safe": True, "message": "Temps look good."}
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=True)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_elevated_user_approves_returns_false(self, mock_require, mock_check, mock_fetch, mock_approval):
        """Elevated temps but user approves — proceed."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is False

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_elevated_user_declines_returns_true(self, mock_require, mock_check, mock_fetch, mock_approval):
        """Elevated temps and user declines — skip."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "CPU hot!"}
        ctx = _make_ctx(lhm_available=True)
        assert run_thermal_guard("TestPhase", ctx) is True

    @patch("src.pipeline.thermal_gate.prompt_approval", return_value=False)
    @patch("src.pipeline.thermal_gate.fetch_snapshot")
    @patch("src.pipeline.thermal_gate.check_idle_thermals")
    @patch("src.pipeline.thermal_gate.require_thermal_protection", return_value=False)
    def test_custom_skip_message(self, mock_require, mock_check, mock_fetch, mock_approval, capsys):
        """Custom skip message is printed."""
        mock_fetch.return_value = {"cpu": 85.0}
        mock_check.return_value = {"safe": False, "message": "hot"}
        ctx = _make_ctx(lhm_available=True)
        run_thermal_guard("TestPhase", ctx, skip_message="Custom skip msg")
        out = capsys.readouterr().out
        assert "Custom skip msg" in out
