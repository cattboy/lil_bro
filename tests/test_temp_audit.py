import pytest
from unittest.mock import patch
from src.scanners.temp_audit import _format_size, scan_temp_folders

def test_format_size():
    assert _format_size(1048576) == "1.00 MB" # 1 MB
    assert _format_size(1048576 * 500) == "500.00 MB" # 500 MB
    assert _format_size(1073741824 * 2) == "2.00 GB" # 2 GB

@patch('src.scanners.temp_audit.scan_dir_size')
def test_scan_temp_folders(mock_scan_dir):
    # Mocking (size_bytes, item_count)
    # Simulate User Temp returning 50MB, others 0
    mock_scan_dir.side_effect = [
        (1048576 * 50, 100), # User Temp
        (0, 0),             # Win Temp
        (0, 0)              # Win Update
    ]
    
    result = scan_temp_folders()
    assert result["total_bytes"] == 1048576 * 50
    assert result["details"]["User Temp"]["file_count"] == 100
