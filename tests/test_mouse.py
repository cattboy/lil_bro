import pytest
from unittest.mock import patch, MagicMock
from src.agent_tools.mouse import check_polling_rate

@patch('src.agent_tools.mouse._fallback_measure_rate')
def test_check_polling_rate_optimal(mock_measure):
    mock_measure.return_value = 1000
    result = check_polling_rate()
    assert result["status"] == "OK"
    assert result["current_hz"] == 1000

@patch('src.agent_tools.mouse._fallback_measure_rate')
def test_check_polling_rate_acceptable(mock_measure):
    mock_measure.return_value = 500
    result = check_polling_rate()
    assert result["status"] == "OK"
    assert result["current_hz"] == 500

@patch('src.agent_tools.mouse._fallback_measure_rate')
def test_check_polling_rate_warning(mock_measure):
    mock_measure.return_value = 125
    result = check_polling_rate()
    assert result["status"] == "WARNING"
    assert "adds input lag" in result["message"]
