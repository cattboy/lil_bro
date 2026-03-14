import pytest
from unittest.mock import patch, MagicMock
from src.agent_tools.game_mode import get_game_mode_status, check_game_mode
from src.utils.errors import ScannerError

@patch('src.scanners.game_mode.winreg')
def test_get_game_mode_enabled(mock_winreg):
    # Setup mock dictionary return
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (1, 4) # 4 is REG_DWORD
    
    assert get_game_mode_status() is True

@patch('src.scanners.game_mode.winreg')
def test_get_game_mode_disabled(mock_winreg):
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (0, 4)
    
    assert get_game_mode_status() is False

@patch('src.scanners.game_mode.winreg')
def test_get_game_mode_missing_key(mock_winreg):
    mock_winreg.OpenKey.side_effect = FileNotFoundError()
    # Missing key implies default behavior (Enabled)
    assert get_game_mode_status() is True

@patch('src.scanners.game_mode.get_game_mode_status')
def test_check_game_mode_ok(mock_get_status):
    mock_get_status.return_value = True
    result = check_game_mode()
    assert result["status"] == "OK"
    assert result["enabled"] is True

@patch('src.scanners.game_mode.get_game_mode_status')
def test_check_game_mode_warning(mock_get_status):
    mock_get_status.return_value = False
    result = check_game_mode()
    assert result["status"] == "WARNING"
    assert result["enabled"] is False

@patch('src.scanners.game_mode.get_game_mode_status')
def test_check_game_mode_error(mock_get_status):
    mock_get_status.side_effect = ScannerError("Registry locked")
    result = check_game_mode()
    assert result["status"] == "ERROR"
