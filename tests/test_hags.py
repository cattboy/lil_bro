import pytest
from unittest.mock import patch, MagicMock
from src.agent_tools.hags import get_hags_status, analyze_hags, set_hags
from src.utils.errors import ScannerError


@patch('src.agent_tools.hags.winreg')
def test_get_hags_enabled(mock_winreg):
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (2, 4)  # 4 = REG_DWORD; 2 = HAGS on
    assert get_hags_status() == {"enabled": True, "supported": True}


@patch('src.agent_tools.hags.winreg')
def test_get_hags_disabled(mock_winreg):
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (1, 4)  # 1 = HAGS off
    assert get_hags_status() == {"enabled": False, "supported": True}


@patch('src.agent_tools.hags.winreg')
def test_get_hags_value_missing_is_unsupported(mock_winreg):
    # HwSchMode value absent -> feature not exposed by this GPU/driver.
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.side_effect = FileNotFoundError()
    assert get_hags_status() == {"enabled": False, "supported": False}


@patch('src.agent_tools.hags.winreg')
def test_get_hags_key_missing_is_unsupported(mock_winreg):
    mock_winreg.OpenKey.side_effect = FileNotFoundError()
    assert get_hags_status() == {"enabled": False, "supported": False}


@patch('src.agent_tools.hags.action_logger')
@patch('src.agent_tools.hags.winreg')
def test_set_hags_enable(mock_winreg, mock_logger):
    mock_key = MagicMock()
    mock_winreg.CreateKeyEx.return_value.__enter__.return_value = mock_key
    mock_winreg.REG_DWORD = 4

    assert set_hags(True) is True
    mock_winreg.SetValueEx.assert_called_once_with(mock_key, "HwSchMode", 0, 4, 2)
    mock_logger.log_action.assert_called_once_with(
        "HAGS", "Set HwSchMode = 2", r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    )


@patch('src.agent_tools.hags.action_logger')
@patch('src.agent_tools.hags.winreg')
def test_set_hags_disable(mock_winreg, mock_logger):
    mock_key = MagicMock()
    mock_winreg.CreateKeyEx.return_value.__enter__.return_value = mock_key
    mock_winreg.REG_DWORD = 4

    assert set_hags(False) is True
    mock_winreg.SetValueEx.assert_called_once_with(mock_key, "HwSchMode", 0, 4, 1)
    mock_logger.log_action.assert_called_once_with(
        "HAGS", "Set HwSchMode = 1", r"HKLM\SYSTEM\CurrentControlSet\Control\GraphicsDrivers"
    )


@patch('src.agent_tools.hags.winreg')
def test_set_hags_failure(mock_winreg):
    mock_winreg.CreateKeyEx.side_effect = PermissionError("Access denied")
    with pytest.raises(ScannerError):
        set_hags(True)


def test_analyze_hags_disabled_can_auto_fix():
    result = analyze_hags({"HAGS": {"enabled": False, "supported": True}})
    assert result["status"] == "WARNING"
    assert result["can_auto_fix"] is True


def test_analyze_hags_enabled_ok():
    result = analyze_hags({"HAGS": {"enabled": True, "supported": True}})
    assert result["status"] == "OK"
    assert result["can_auto_fix"] is False


def test_analyze_hags_unsupported_skipped():
    result = analyze_hags({"HAGS": {"enabled": False, "supported": False}})
    assert result["status"] == "SKIPPED"
    assert result["can_auto_fix"] is False


def test_analyze_hags_collection_error_skipped():
    result = analyze_hags({"HAGS": {"error": "registry read failed"}})
    assert result["status"] == "SKIPPED"


def test_analyze_hags_missing_section_skipped():
    result = analyze_hags({})
    assert result["status"] == "SKIPPED"
