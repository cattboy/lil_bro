import pytest
from unittest.mock import patch, MagicMock
from src.bootstrapper import is_admin, check_admin, create_restore_point
from src.utils.errors import AdminRequiredError, RestorePointError

@patch('src.bootstrapper.ctypes.windll.shell32.IsUserAnAdmin')
def test_is_admin_true(mock_is_admin):
    mock_is_admin.return_value = 1
    assert is_admin() is True

@patch('src.bootstrapper.ctypes.windll.shell32.IsUserAnAdmin')
def test_is_admin_false(mock_is_admin):
    mock_is_admin.return_value = 0
    assert is_admin() is False

@patch('src.bootstrapper.is_admin')
def test_check_admin_raises(mock_is_admin):
    mock_is_admin.return_value = False
    with pytest.raises(AdminRequiredError):
        check_admin()

@patch('src.bootstrapper.prompt_approval')
@patch('src.bootstrapper.subprocess.run')
def test_create_restore_point_success(mock_run, mock_prompt):
    mock_prompt.return_value = True
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result
    
    result = create_restore_point()
    assert result is True
    mock_run.assert_called_once()

@patch('src.bootstrapper.prompt_approval')
def test_create_restore_point_rejected(mock_prompt):
    mock_prompt.return_value = False
    result = create_restore_point()
    assert result is False
