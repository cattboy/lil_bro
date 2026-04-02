import pytest
from unittest.mock import patch, MagicMock
from src.agent_tools.game_mode import get_game_mode_status, analyze_game_mode, set_game_mode
from src.utils.errors import ScannerError

@patch('src.agent_tools.game_mode.winreg')
def test_get_game_mode_enabled(mock_winreg):
    # Setup mock dictionary return
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (1, 4) # 4 is REG_DWORD

    assert get_game_mode_status() is True

@patch('src.agent_tools.game_mode.winreg')
def test_get_game_mode_disabled(mock_winreg):
    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__.return_value = mock_key
    mock_winreg.QueryValueEx.return_value = (0, 4)

    assert get_game_mode_status() is False

@patch('src.agent_tools.game_mode.winreg')
def test_get_game_mode_missing_key(mock_winreg):
    mock_winreg.OpenKey.side_effect = FileNotFoundError()
    # Missing key implies default behavior (Enabled)
    assert get_game_mode_status() is True


@patch('src.agent_tools.game_mode.action_logger')
@patch('src.agent_tools.game_mode.winreg')
def test_set_game_mode_enable(mock_winreg, mock_logger):
    mock_key = MagicMock()
    mock_winreg.CreateKeyEx.return_value.__enter__.return_value = mock_key
    mock_winreg.REG_DWORD = 4

    result = set_game_mode(True)

    assert result is True
    mock_winreg.SetValueEx.assert_called_once_with(mock_key, "AutoGameModeEnabled", 0, 4, 1)
    mock_logger.log_action.assert_called_once_with(
        "Game Mode", "Set AutoGameModeEnabled = 1", r"HKCU\SOFTWARE\Microsoft\GameBar"
    )


@patch('src.agent_tools.game_mode.action_logger')
@patch('src.agent_tools.game_mode.winreg')
def test_set_game_mode_disable(mock_winreg, mock_logger):
    mock_key = MagicMock()
    mock_winreg.CreateKeyEx.return_value.__enter__.return_value = mock_key
    mock_winreg.REG_DWORD = 4

    result = set_game_mode(False)

    assert result is True
    mock_winreg.SetValueEx.assert_called_once_with(mock_key, "AutoGameModeEnabled", 0, 4, 0)
    mock_logger.log_action.assert_called_once_with(
        "Game Mode", "Set AutoGameModeEnabled = 0", r"HKCU\SOFTWARE\Microsoft\GameBar"
    )


@patch('src.agent_tools.game_mode.winreg')
def test_set_game_mode_failure(mock_winreg):
    mock_winreg.CreateKeyEx.side_effect = PermissionError("Access denied")

    with pytest.raises(ScannerError):
        set_game_mode(True)


def test_analyze_game_mode_can_auto_fix():
    result = analyze_game_mode({"GameMode": {"enabled": False}})
    assert result["status"] == "WARNING"
    assert result["can_auto_fix"] is True
