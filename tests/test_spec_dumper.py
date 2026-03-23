import pytest
from unittest.mock import patch, MagicMock
from src.collectors.sub.nvidia_smi_dumper import get_nvidia_smi


@patch("src.collectors.sub.nvidia_smi_dumper.subprocess.run")
@patch("src.collectors.sub.nvidia_smi_dumper.ET")
def test_get_nvidia_smi_success(mock_et, mock_run):
    mock_run.return_value = MagicMock(stdout="<xml/>")

    mock_root = MagicMock()
    mock_root.findtext.return_value = "470.57"  # driver_version

    mock_gpu = MagicMock()
    mock_gpu.findtext.side_effect = lambda x: {
        "product_name": "RTX 3080",
        "bar1_memory_usage/used": "512 MiB",
        "pci/pci_gpu_link_info/link_widths/max_link_width": "16x",
        "pci/pci_gpu_link_info/link_widths/current_link_width": "16x",
    }[x]
    mock_root.findall.return_value = [mock_gpu]
    mock_et.fromstring.return_value = mock_root

    result = get_nvidia_smi()
    assert isinstance(result, list)
    assert result[0]["GPU"] == "RTX 3080"
    assert result[0]["Driver"] == "470.57"
    assert result[0]["BAR1 Used (MiB)"] == 512
    assert result[0]["PCIe Max Width"] == 16
    assert result[0]["PCIe Current Width"] == 16
    assert result[0]["ReBAR"] is True  # 512 > 256


@patch("src.collectors.sub.nvidia_smi_dumper.subprocess.run", side_effect=FileNotFoundError)
def test_get_nvidia_smi_not_found(mock_run):
    with pytest.raises(FileNotFoundError, match="nvidia-smi executable not found"):
        get_nvidia_smi()


@patch("src.collectors.sub.nvidia_smi_dumper.subprocess.run", side_effect=Exception("test error"))
def test_get_nvidia_smi_other_exception(mock_run):
    with pytest.raises(Exception, match="test error"):
        get_nvidia_smi()
