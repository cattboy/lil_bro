import pytest
import subprocess
from unittest.mock import patch, MagicMock
from src.agent_tools.power_plan import (
    get_active_power_plan,
    list_available_plans,
    set_active_plan,
    create_high_performance_plan,
    analyze_power_plan,
)
from src.utils.errors import ScannerError

@patch('src.agent_tools.power_plan.subprocess.run')
def test_get_active_power_plan_balanced(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)"
    mock_run.return_value = mock_result

    guid, name = get_active_power_plan()
    assert guid == "381b4222-f694-41f0-9685-ff5bb260df2e"
    assert name == "Balanced"

@patch('src.agent_tools.power_plan.subprocess.run')
def test_get_active_power_plan_high_perf(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (High performance)"
    mock_run.return_value = mock_result

    guid, name = get_active_power_plan()
    assert guid == "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    assert name == "High performance"

@patch('src.agent_tools.power_plan.subprocess.run')
def test_get_active_power_plan_missing_executable(mock_run):
    mock_run.side_effect = FileNotFoundError()
    with pytest.raises(ScannerError):
        get_active_power_plan()

@patch('src.agent_tools.power_plan.subprocess.run')
def test_list_available_plans(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = """
Existing Power Schemes (* Active)
-----------------------------------
Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced) *
Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (High performance)
"""
    mock_run.return_value = mock_result

    plans = list_available_plans()
    assert len(plans) == 2
    assert plans[0] == ("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced")
    assert plans[1] == ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "High performance")

@patch('src.agent_tools.power_plan.subprocess.run')
def test_set_active_plan(mock_run):
    set_active_plan("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
    mock_run.assert_called_with(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], capture_output=True, text=True, check=True)

@patch('src.agent_tools.power_plan.subprocess.run')
def test_create_high_performance_plan(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Power Scheme GUID: 12345678-1234-1234-1234-123456789abc  (High performance)"
    mock_run.return_value = mock_result

    guid, name = create_high_performance_plan()
    assert guid == "12345678-1234-1234-1234-123456789abc"
    assert name == "High performance"


# --- analyze_power_plan tests ---

def test_analyze_power_plan_high_perf():
    """High Performance GUID detected -> OK."""
    specs = {"PowerPlan": {"guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "name": "High performance"}}
    result = analyze_power_plan(specs)
    assert result["status"] == "OK"
    assert result["current"] == "High performance"
    assert result["can_auto_fix"] is False


def test_analyze_power_plan_ultimate():
    """Ultimate Performance detected by name -> OK."""
    specs = {"PowerPlan": {"guid": "e9a42b02-d5df-448d-aa00-03f14749eb61", "name": "Ultimate Performance"}}
    result = analyze_power_plan(specs)
    assert result["status"] == "OK"


def test_analyze_power_plan_balanced_warning():
    """Non-performance plan -> WARNING with auto-fix."""
    specs = {"PowerPlan": {"guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced"}}
    result = analyze_power_plan(specs)
    assert result["status"] == "WARNING"
    assert result["can_auto_fix"] is True
    assert result["current"] == "Balanced"


def test_analyze_power_plan_unknown():
    """Empty specs -> WARNING (defaults to non-performance)."""
    result = analyze_power_plan({})
    assert result["status"] == "WARNING"
    assert result["can_auto_fix"] is True
