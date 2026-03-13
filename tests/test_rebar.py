import pytest
from unittest.mock import patch, MagicMock
from src.scanners.rebar import check_rebar

@patch('src.scanners.rebar.wmi.WMI')
def test_check_rebar_enabled(mock_wmi):
    mock_c = MagicMock()
    
    # Needs a memory range > 256MB
    mock_mem = MagicMock()
    mock_mem.StartingAddress = "0"
    mock_mem.EndingAddress = str((1024 * 1024 * 1024) - 1) # 1024 MB - 1
    
    mock_c.Win32_DeviceMemoryAddress.return_value = [mock_mem]
    mock_wmi.return_value = mock_c
    
    result = check_rebar()
    assert result["rebar_enabled"] is True
    assert result["max_range_mb"] == 1024.0
    assert result["status"] == "OK"

@patch('src.scanners.rebar.wmi.WMI')
def test_check_rebar_disabled(mock_wmi):
    mock_c = MagicMock()
    
    # Only small ranges
    mock_mem = MagicMock()
    mock_mem.StartingAddress = "0"
    mock_mem.EndingAddress = str((256 * 1024 * 1024) - 1) # Exact 256MB - 1
    
    mock_c.Win32_DeviceMemoryAddress.return_value = [mock_mem]
    mock_wmi.return_value = mock_c
    
    result = check_rebar()
    assert result["rebar_enabled"] is False
    assert result["max_range_mb"] == 256.0
    assert result["status"] == "WARNING"

@patch('src.scanners.rebar.wmi.WMI')
def test_check_rebar_wmi_error(mock_wmi):
    mock_wmi.side_effect = Exception("WMI failed")
    
    result = check_rebar()
    assert result["status"] == "ERROR"
    assert "WMI failed" in result["message"]
