import os
import pytest
from unittest.mock import patch
from src.agent_tools.temp_audit import _format_size, analyze_temp_folders, clean_temp_folders

def test_format_size():
    assert _format_size(1048576) == "1.00 MB" # 1 MB
    assert _format_size(1048576 * 500) == "500.00 MB" # 500 MB
    assert _format_size(1073741824 * 2) == "2.00 GB" # 2 GB

@patch('src.agent_tools.temp_audit.os.walk')
@patch('src.agent_tools.temp_audit.os.path.exists')
@patch('src.agent_tools.temp_audit.os.path.getsize')
@patch('src.agent_tools.temp_audit.os.remove')
def test_clean_temp_folders(mock_remove, mock_getsize, mock_exists, mock_walk):
    from src.agent_tools.temp_audit import clean_temp_folders

    mock_exists.return_value = True
    # Simulate os.walk yielding one file
    mock_walk.return_value = [('/fake/dir', [], ['file1.tmp'])]
    mock_getsize.return_value = 1024 # 1 KB per file

    details = {
        "User Temp": {"path": "/fake/dir", "size_bytes": 1024, "file_count": 1},
        "Win Temp": {"path": "/fake/win", "size_bytes": 0, "file_count": 0}
    }

    bytes_freed, files_deleted = clean_temp_folders(details)

    assert bytes_freed == 1024
    assert files_deleted == 1
    mock_remove.assert_called_once_with(os.path.join('/fake/dir', 'file1.tmp'))


@patch('src.agent_tools.temp_audit.os.walk')
@patch('src.agent_tools.temp_audit.os.path.exists')
@patch('src.agent_tools.temp_audit.os.path.getsize')
@patch('src.agent_tools.temp_audit.os.remove')
def test_clean_temp_folders_permission_error(mock_remove, mock_getsize, mock_exists, mock_walk):
    mock_exists.return_value = True
    mock_walk.return_value = [('/fake/dir', [], ['file1.tmp', 'file2.tmp'])]
    mock_getsize.return_value = 1024
    mock_remove.side_effect = [PermissionError("Access denied"), None]

    details = {"User Temp": {"path": "/fake/dir", "size_bytes": 2048, "file_count": 2}}

    bytes_freed, files_deleted = clean_temp_folders(details)

    assert files_deleted == 1
    assert bytes_freed == 1024


@patch('src.agent_tools.temp_audit.os.walk')
@patch('src.agent_tools.temp_audit.os.path.exists')
@patch('src.agent_tools.temp_audit.os.path.getsize')
@patch('src.agent_tools.temp_audit.os.remove')
def test_clean_temp_folders_locked_file(mock_remove, mock_getsize, mock_exists, mock_walk):
    mock_exists.return_value = True
    mock_walk.return_value = [('/fake/dir', [], ['locked.tmp', 'ok.tmp'])]
    mock_getsize.return_value = 512
    mock_remove.side_effect = [OSError("File in use"), None]

    details = {"User Temp": {"path": "/fake/dir", "size_bytes": 1024, "file_count": 2}}

    bytes_freed, files_deleted = clean_temp_folders(details)

    assert files_deleted == 1
    assert bytes_freed == 512


def test_analyze_temp_folders_under_threshold():
    specs = {"TempFolders": {"total_bytes": 500 * 1024 * 1024, "details": {}}}
    result = analyze_temp_folders(specs)
    assert result["status"] == "OK"
    assert result["check"] == "temp_folders"
