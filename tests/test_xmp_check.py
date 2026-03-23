import pytest
from unittest.mock import patch, MagicMock
from src.agent_tools.xmp_check import get_memory_speeds, check_xmp_status
from src.utils.errors import ScannerError

@patch('src.agent_tools.xmp_check.wmi.WMI')
def test_get_memory_speeds(mock_wmi):
    mock_c = MagicMock()
    mock_module = MagicMock()
    mock_module.ConfiguredClockSpeed = 3200
    mock_module.Speed = 2133
    mock_c.Win32_PhysicalMemory.return_value = [mock_module]
    mock_wmi.return_value = mock_c
    
    conf, base = get_memory_speeds()
    assert conf == 3200
    assert base == 2133

@patch('src.agent_tools.xmp_check.wmi.WMI')
def test_get_memory_speeds_missing_module(mock_wmi):
    mock_c = MagicMock()
    mock_c.Win32_PhysicalMemory.return_value = []
    mock_wmi.return_value = mock_c
    
    with pytest.raises(ScannerError):
        get_memory_speeds()

@patch('src.agent_tools.xmp_check.get_memory_speeds')
def test_check_xmp_status_enabled_diff(mock_speeds):
    mock_speeds.return_value = (3600, 2666) # Configured > Base
    result = check_xmp_status()
    assert result["xmp_likely"] is True
    assert result["status"] == "OK"

@patch('src.agent_tools.xmp_check.get_memory_speeds')
def test_check_xmp_status_enabled_heuristic_ddr5(mock_speeds):
    mock_speeds.return_value = (6000, 6000) # Same, but high speed
    result = check_xmp_status()
    assert result["xmp_likely"] is True
    assert result["status"] == "OK"

@patch('src.agent_tools.xmp_check.get_memory_speeds')
def test_check_xmp_status_disabled_heuristic_ddr4(mock_speeds):
    mock_speeds.return_value = (2133, 2133) # Same, low speed DDR4
    result = check_xmp_status()
    assert result["xmp_likely"] is False
    assert result["status"] == "WARNING"

@patch('src.agent_tools.xmp_check.get_memory_speeds')
def test_check_xmp_status_disabled_heuristic_ddr5(mock_speeds):
    mock_speeds.return_value = (4800, 4800) # Same, low speed DDR5
    result = check_xmp_status()
    assert result["xmp_likely"] is False
    assert result["status"] == "WARNING"

@patch('src.agent_tools.xmp_check.get_memory_speeds')
def test_check_xmp_status_error(mock_speeds):
    mock_speeds.side_effect = ScannerError("WMI Dead")
    result = check_xmp_status()
    assert result["status"] == "ERROR"
