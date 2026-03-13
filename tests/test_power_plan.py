import pytest
import subprocess
from unittest.mock import patch, MagicMock
from src.scanners.power_plan import get_active_power_plan, check_power_plan
from src.utils.errors import ScannerError

@patch('src.scanners.power_plan.subprocess.run')
def test_get_active_power_plan_balanced(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced)"
    mock_run.return_value = mock_result
    
    guid, name = get_active_power_plan()
    assert guid == "381b4222-f694-41f0-9685-ff5bb260df2e"
    assert name == "Balanced"

@patch('src.scanners.power_plan.subprocess.run')
def test_get_active_power_plan_high_perf(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Power Scheme GUID: 8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c  (High performance)"
    mock_run.return_value = mock_result
    
    guid, name = get_active_power_plan()
    assert guid == "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"
    assert name == "High performance"

@patch('src.scanners.power_plan.subprocess.run')
def test_get_active_power_plan_missing_executable(mock_run):
    mock_run.side_effect = FileNotFoundError()
    with pytest.raises(ScannerError):
        get_active_power_plan()

@patch('src.scanners.power_plan.get_active_power_plan')
def test_check_power_plan_ok(mock_get_plan):
    mock_get_plan.return_value = ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "High performance")
    result = check_power_plan()
    assert result["status"] == "OK"

@patch('src.scanners.power_plan.get_active_power_plan')
def test_check_power_plan_warning(mock_get_plan):
    mock_get_plan.return_value = ("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced")
    result = check_power_plan()
    assert result["status"] == "WARNING"

@patch('src.scanners.power_plan.get_active_power_plan')
def test_check_power_plan_error(mock_get_plan):
    mock_get_plan.side_effect = ScannerError("Command failed")
    result = check_power_plan()
    assert result["status"] == "ERROR"
