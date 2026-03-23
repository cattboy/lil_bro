import pytest
from unittest.mock import patch
from src.agent_tools.temp_audit import _format_size, scan_temp_folders

def test_format_size():
    assert _format_size(1048576) == "1.00 MB" # 1 MB
    assert _format_size(1048576 * 500) == "500.00 MB" # 500 MB
    assert _format_size(1073741824 * 2) == "2.00 GB" # 2 GB

@patch('src.agent_tools.temp_audit.scan_dir_size')
def test_scan_temp_folders(mock_scan_dir):
    # Mocking (size_bytes, item_count) for 14 targets
    mock_scan_dir.side_effect = [
        (1048576 * 50, 100), # User Temp
        (0, 0),             # Win Temp
        (0, 0),             # Update Cache
        (0, 0),             # NVIDIA Shader Cache
        (0, 0),             # NVIDIA GL Cache
        (0, 0),             # NVIDIA DX Cache
        (0, 0),             # NVIDIA Compute Cache
        (0, 0),             # D3D Cache
        (0, 0),             # NVIDIA Per Driver Version DX Cache
        (0, 0),             # AMD DX Cache
        (0, 0),             # AMD DX9 Cache
        (0, 0),             # AMD Dxc Cache
        (0, 0),             # AMD Ogl Cache
        (0, 0),             # Intel D3D Cache
    ]
    
    result = scan_temp_folders()
    assert result["total_bytes"] == 1048576 * 50
    assert result["details"]["User Temp"]["file_count"] == 100

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
    mock_remove.assert_called_once_with('/fake/dir/file1.tmp')
