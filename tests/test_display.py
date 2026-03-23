import pytest
from unittest.mock import patch, MagicMock
from src.agent_tools.display import get_current_refresh_rate, check_refresh_rate, analyze_display
from src.utils.errors import ScannerError

@patch('src.agent_tools.display.wmi.WMI')
def test_get_current_refresh_rate(mock_wmi):
    mock_c = MagicMock()
    mock_controller = MagicMock()
    mock_controller.CurrentRefreshRate = 144
    mock_c.Win32_VideoController.return_value = [mock_controller]
    mock_wmi.return_value = mock_c
    
    assert get_current_refresh_rate() == 144

@patch('src.agent_tools.display.get_current_refresh_rate')
def test_check_refresh_rate_ok(mock_get_rr):
    mock_get_rr.return_value = 144
    result = check_refresh_rate()
    assert result["status"] == "OK"
    assert result["current_hz"] == 144

@patch('src.agent_tools.display.get_current_refresh_rate')
def test_check_refresh_rate_warning(mock_get_rr):
    mock_get_rr.return_value = 60
    result = check_refresh_rate()
    assert result["status"] == "WARNING"
    assert result["current_hz"] == 60

@patch('src.agent_tools.display.get_current_refresh_rate')
def test_check_refresh_rate_error(mock_get_rr):
    mock_get_rr.side_effect = ScannerError("WMI Failure")
    result = check_refresh_rate()
    assert result["status"] == "ERROR"


def test_analyze_display_ok():
    specs = {"DisplayCapabilities": [
        {"current_refresh_hz": 144, "max_refresh_hz": 144, "edid_declared_max_hz": None}
    ]}
    result = analyze_display(specs)
    assert result["status"] == "OK"
    assert result["current"] == 144


def test_analyze_display_warning_mismatch():
    specs = {"DisplayCapabilities": [
        {"current_refresh_hz": 60, "max_refresh_hz": 144, "edid_declared_max_hz": None}
    ]}
    result = analyze_display(specs)
    assert result["status"] == "WARNING"
    assert result["can_auto_fix"] is True
    assert result["expected"] == 144


def test_analyze_display_missing_capabilities():
    specs = {"DisplayCapabilities": []}
    result = analyze_display(specs)
    assert result["check"] == "display"
    assert result["status"] == "ERROR"


def test_analyze_display_multi_monitor():
    # Only the primary (first) display is evaluated
    specs = {"DisplayCapabilities": [
        {"current_refresh_hz": 60, "max_refresh_hz": 144, "edid_declared_max_hz": None},  # primary: WARNING
        {"current_refresh_hz": 144, "max_refresh_hz": 144, "edid_declared_max_hz": None},  # secondary: OK
    ]}
    result = analyze_display(specs)
    assert result["check"] == "display"
    assert result["status"] == "WARNING"
    assert result["expected"] == 144
