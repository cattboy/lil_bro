import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.bootstrapper import is_admin, check_admin, create_restore_point
from src.utils.errors import AdminRequiredError, RestorePointError

FIXED_DT = datetime(2026, 4, 1, 14, 32, 7)
FIXED_DESC = "lil_bro Pre-Tuning 2026-04-01 14:32:07"

@patch('src.utils.platform.ctypes.windll.shell32.IsUserAnAdmin')
def test_is_admin_true(mock_is_admin):
    mock_is_admin.return_value = 1
    assert is_admin() is True

@patch('src.utils.platform.ctypes.windll.shell32.IsUserAnAdmin')
def test_is_admin_false(mock_is_admin):
    mock_is_admin.return_value = 0
    assert is_admin() is False

@patch('src.bootstrapper.is_admin')
def test_check_admin_raises(mock_is_admin):
    mock_is_admin.return_value = False
    with pytest.raises(AdminRequiredError):
        check_admin()

@patch('src.bootstrapper.datetime')
@patch('src.bootstrapper.is_system_restore_enabled')
@patch('src.bootstrapper.prompt_approval')
@patch('src.bootstrapper.subprocess.run')
def test_create_restore_point_success(mock_run, mock_prompt, mock_is_enabled, mock_dt):
    mock_dt.now.return_value = FIXED_DT
    mock_is_enabled.return_value = True
    mock_prompt.return_value = True

    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = create_restore_point()
    assert result is True
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert FIXED_DESC in " ".join(call_args)

@patch('src.bootstrapper.datetime')
@patch('src.bootstrapper.is_system_restore_enabled')
@patch('src.bootstrapper.prompt_approval')
def test_create_restore_point_rejected(mock_prompt, mock_is_enabled, mock_dt):
    mock_dt.now.return_value = FIXED_DT
    mock_is_enabled.return_value = True
    mock_prompt.return_value = False
    result = create_restore_point()
    assert result is False



@patch('src.bootstrapper.datetime')
@patch('src.bootstrapper.is_system_restore_enabled')
@patch('src.bootstrapper.prompt_approval')
@patch('src.bootstrapper.subprocess.run')
def test_create_restore_point_assume_approved_skips_prompt(mock_run, mock_prompt, mock_is_enabled, mock_dt):
    """assume_approved=True creates the point with no prompt_approval gate."""
    mock_dt.now.return_value = FIXED_DT
    mock_is_enabled.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = create_restore_point(assume_approved=True)
    assert result is True
    mock_prompt.assert_not_called()
    mock_run.assert_called_once()


@patch('src.bootstrapper.datetime')
@patch('src.bootstrapper.enable_system_restore')
@patch('src.bootstrapper.is_system_restore_enabled')
@patch('src.bootstrapper.prompt_approval')
@patch('src.bootstrapper.subprocess.run')
def test_create_restore_point_assume_approved_enables_when_disabled(
    mock_run, mock_prompt, mock_is_enabled, mock_enable, mock_dt
):
    """assume_approved=True enables System Restore non-interactively when disabled."""
    mock_dt.now.return_value = FIXED_DT
    mock_is_enabled.return_value = False
    mock_enable.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    result = create_restore_point(assume_approved=True)
    assert result is True
    mock_prompt.assert_not_called()
    mock_enable.assert_called_once()
    mock_run.assert_called_once()


@patch('src.bootstrapper.datetime')
@patch('src.bootstrapper.enable_system_restore')
@patch('src.bootstrapper.is_system_restore_enabled')
@patch('src.bootstrapper.prompt_approval')
def test_create_restore_point_assume_approved_enable_fails(
    mock_prompt, mock_is_enabled, mock_enable, mock_dt
):
    """assume_approved=True returns False when enable_system_restore() fails; no prompt called."""
    mock_dt.now.return_value = FIXED_DT
    mock_is_enabled.return_value = False
    mock_enable.return_value = False

    result = create_restore_point(assume_approved=True)
    assert result is False
    mock_prompt.assert_not_called()
    mock_enable.assert_called_once()


@patch('src.bootstrapper.datetime')
@patch('src.bootstrapper.is_system_restore_enabled')
@patch('src.bootstrapper.prompt_approval')
@patch('src.bootstrapper.subprocess.run')
def test_create_restore_point_bypasses_frequency_throttle(mock_run, mock_prompt, mock_is_enabled, mock_dt):
    """PS command must set SystemRestorePointCreationFrequency=0 before Checkpoint-Computer."""
    mock_dt.now.return_value = FIXED_DT
    mock_is_enabled.return_value = True
    mock_prompt.return_value = True
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_run.return_value = mock_result

    create_restore_point()

    ps_cmd = mock_run.call_args[0][0][2]
    assert "SystemRestorePointCreationFrequency" in ps_cmd
    assert "Checkpoint-Computer" in ps_cmd
