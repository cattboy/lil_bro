import pytest
from unittest.mock import patch, MagicMock
from src.scanners.rebar import check_rebar, check_nvidia_rebar, check_wmi_rebar

@patch('src.scanners.rebar.subprocess.run')
def test_check_nvidia_rebar_enabled(mock_run):
    mock_run.return_value = MagicMock(stdout="NVIDIA GeForce RTX 3080, 10240, 10240, 5\\n", returncode=0)
    status, msg = check_nvidia_rebar()
    assert status is True
    assert "ENABLED" in msg

@patch('src.scanners.rebar.subprocess.run')
def test_check_nvidia_rebar_disabled(mock_run):
    mock_run.return_value = MagicMock(stdout="NVIDIA GeForce RTX 3080, 10240, 256, 5\\n", returncode=0)
    status, msg = check_nvidia_rebar()
    assert status is False
    assert "DISABLED" in msg

@patch('src.scanners.rebar.subprocess.run')
def test_check_nvidia_rebar_not_found(mock_run):
    mock_run.side_effect = FileNotFoundError()
    status, msg = check_nvidia_rebar()
    assert status is None
    assert "not found" in msg

@patch('src.scanners.rebar.wmi.WMI')
def test_check_wmi_rebar_enabled(mock_wmi):
    mock_c = MagicMock()
    mock_mem = MagicMock()
    mock_mem.StartingAddress = "0"
    mock_mem.EndingAddress = str((1024 * 1024 * 1024) - 1)
    mock_c.Win32_DeviceMemoryAddress.return_value = [mock_mem]
    mock_wmi.return_value = mock_c
    
    status, max_mb, msg = check_wmi_rebar()
    assert status is True
    assert max_mb == 1024.0

@patch('src.scanners.rebar.wmi.WMI')
def test_check_wmi_rebar_disabled(mock_wmi):
    mock_c = MagicMock()
    mock_mem = MagicMock()
    mock_mem.StartingAddress = "0"
    mock_mem.EndingAddress = str((256 * 1024 * 1024) - 1)
    mock_c.Win32_DeviceMemoryAddress.return_value = [mock_mem]
    mock_wmi.return_value = mock_c
    
    status, max_mb, msg = check_wmi_rebar()
    assert status is False
    assert max_mb == 256.0

@patch('src.scanners.rebar.check_nvidia_rebar')
@patch('src.scanners.rebar.check_wmi_rebar')
def test_check_rebar_nvidia_wins(mock_wmi, mock_nv):
    mock_nv.return_value = (True, "NVIDIA ReBAR is ON")
    
    result = check_rebar()
    assert result["rebar_enabled"] is True
    assert "NVIDIA ReBAR is ON" in result["message"]
    mock_wmi.assert_not_called()

@patch('src.scanners.rebar.check_nvidia_rebar')
@patch('src.scanners.rebar.check_wmi_rebar')
def test_check_rebar_wmi_fallback(mock_wmi, mock_nv):
    mock_nv.return_value = (None, "nvidia-smi error")
    mock_wmi.return_value = (True, 1024.0, "WMI ReBAR ON")
    
    result = check_rebar()
    assert result["rebar_enabled"] is True
    assert "WMI ReBAR ON" in result["message"]
    mock_wmi.assert_called_once()

