import pytest
import subprocess
from unittest.mock import patch, MagicMock
from src.scanners.power_plan import (
    get_active_power_plan, 
    check_power_plan, 
    list_available_plans, 
    set_active_plan, 
    create_high_performance_plan
)
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

@patch('src.scanners.power_plan.subprocess.run')
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

@patch('src.scanners.power_plan.subprocess.run')
def test_set_active_plan(mock_run):
    set_active_plan("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")
    mock_run.assert_called_with(["powercfg", "/setactive", "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c"], capture_output=True, text=True, check=True)

@patch('src.scanners.power_plan.subprocess.run')
def test_create_high_performance_plan(mock_run):
    mock_result = MagicMock()
    mock_result.stdout = "Power Scheme GUID: 12345678-1234-1234-1234-123456789abc  (High performance)"
    mock_run.return_value = mock_result
    
    guid, name = create_high_performance_plan()
    assert guid == "12345678-1234-1234-1234-123456789abc"
    assert name == "High performance"

@patch('src.scanners.power_plan.get_active_power_plan')
def test_check_power_plan_ok(mock_get_plan):
    mock_get_plan.return_value = ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "High performance")
    result = check_power_plan()
    assert result["status"] == "OK"

@patch('src.scanners.power_plan.get_active_power_plan')
@patch('src.scanners.power_plan.list_available_plans')
@patch('src.scanners.power_plan.prompt_approval')
@patch('src.scanners.power_plan.set_active_plan')
def test_check_power_plan_switch_success(mock_set, mock_prompt, mock_list, mock_get_plan):
    mock_get_plan.return_value = ("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced")
    mock_list.return_value = [("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "High performance")]
    mock_prompt.return_value = True
    
    result = check_power_plan()
    assert result["status"] == "OK"
    assert result["active_plan"] == "High performance"
    mock_set.assert_called_once_with("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c")

@patch('src.scanners.power_plan.get_active_power_plan')
@patch('src.scanners.power_plan.list_available_plans')
@patch('src.scanners.power_plan.prompt_approval')
def test_check_power_plan_switch_rejected(mock_prompt, mock_list, mock_get_plan):
    mock_get_plan.return_value = ("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced")
    mock_list.return_value = [("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "High performance")]
    mock_prompt.return_value = False
    
    result = check_power_plan()
    assert result["status"] == "WARNING" # Still warning since it wasn't changed

@patch('src.scanners.power_plan.get_active_power_plan')
@patch('src.scanners.power_plan.list_available_plans')
@patch('src.scanners.power_plan.create_high_performance_plan')
@patch('src.scanners.power_plan.prompt_approval')
@patch('src.scanners.power_plan.set_active_plan')
def test_check_power_plan_create_and_switch(mock_set, mock_prompt, mock_create, mock_list, mock_get_plan):
    mock_get_plan.return_value = ("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced")
    mock_list.return_value = [("381b4222-f694-41f0-9685-ff5bb260df2e", "Balanced")] # No HP
    mock_create.return_value = ("new-guid-123", "High performance")
    mock_prompt.return_value = True
    
    result = check_power_plan()
    assert result["status"] == "OK"
    assert result["active_plan"] == "High performance"
    mock_create.assert_called_once()
    mock_set.assert_called_once_with("new-guid-123")

@patch('src.scanners.power_plan.get_active_power_plan')
def test_check_power_plan_error(mock_get_plan):
    mock_get_plan.side_effect = ScannerError("Command failed")
    result = check_power_plan()
    assert result["status"] == "ERROR"
