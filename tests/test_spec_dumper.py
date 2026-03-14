import pytest
from unittest.mock import patch, MagicMock
from src.collectors.spec_dumper import get_nvidia_smi

@patch("src.collectors.spec_dumper.subprocess.run")
@patch("src.collectors.spec_dumper.ET")
def test_get_nvidia_smi_success(mock_et, mock_run):
    # Mock subprocess result
    mock_run.return_value = MagicMock(stdout="<nvidia_smi><gpu><product_name>RTX 3080</product_name><driver_version>470.57</driver_version><bar1_memory_usage><used>512</used></bar1_memory_usage><pci><link_widths><max_link_width>16x</max_link_width><current_link_width>16x</current_link_width></link_widths></pci></gpu></nvidia_smi>")
    
    # Mock XML parsing
    mock_root = MagicMock()
    mock_gpu = MagicMock()
    mock_gpu.findtext.side_effect = lambda x: {
        "product_name": "RTX 3080",
        "driver_version": "470.57",
        "bar1_memory_usage/used": "512",
        "pci/link_widths/max_link_width": "16x",
        "pci/link_widths/current_link_width": "16x"
    }[x]
    mock_root.findall.return_value = [mock_gpu]
    mock_et.fromstring.return_value = mock_root

    result = get_nvidia_smi()
    assert isinstance(result, list)
    assert result[0]["GPU"] == "RTX 3080"
    assert result[0]["Driver"] == "470.57"
    assert result[0]["BAR1 Used MiB"] == "512"
    assert result[0]["Link Width Max"] == "16x"
    assert result[0]["Link Width Current"] == "16x"
    assert result[0]["ReBAR"] == "Enabled"

@patch("src.collectors.spec_dumper.subprocess.run", side_effect=FileNotFoundError)
def test_get_nvidia_smi_not_found(mock_run):
    result = get_nvidia_smi()
    assert result == "nvidia-smi not found"

@patch("src.collectors.spec_dumper.subprocess.run", side_effect=Exception("test error"))
def test_get_nvidia_smi_other_exception(mock_run):
    result = get_nvidia_smi()
    assert result.startswith("nvidia-smi error:")