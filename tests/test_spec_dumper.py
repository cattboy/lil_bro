import json
import pytest
from unittest.mock import patch, MagicMock
from src.collectors.sub.nvidia_smi_dumper import get_nvidia_smi
from src.collectors.spec_dumper import dump_system_specs


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


@patch("src.collectors.sub.nvidia_smi_dumper.subprocess.run")
@patch("src.collectors.sub.nvidia_smi_dumper.ET")
def test_get_nvidia_smi_multi_gpu(mock_et, mock_run):
    mock_run.return_value = MagicMock(stdout="<xml/>")
    mock_root = MagicMock()
    mock_root.findtext.return_value = "535.00"

    def make_gpu(name):
        gpu = MagicMock()
        gpu.findtext.side_effect = lambda x: {
            "product_name": name,
            "bar1_memory_usage/used": "512 MiB",
            "pci/pci_gpu_link_info/link_widths/max_link_width": "16x",
            "pci/pci_gpu_link_info/link_widths/current_link_width": "16x",
        }.get(x)
        return gpu

    mock_root.findall.return_value = [make_gpu("RTX 3080"), make_gpu("RTX 3090")]
    mock_et.fromstring.return_value = mock_root

    result = get_nvidia_smi()
    assert len(result) == 2
    assert result[0]["GPU"] == "RTX 3080"
    assert result[1]["GPU"] == "RTX 3090"
    assert result[0]["Driver"] == "535.00"


@patch("src.collectors.sub.nvidia_smi_dumper.subprocess.run")
@patch("src.collectors.sub.nvidia_smi_dumper.ET")
def test_get_nvidia_smi_missing_fields(mock_et, mock_run):
    mock_run.return_value = MagicMock(stdout="<xml/>")
    mock_root = MagicMock()
    mock_root.findtext.return_value = "535.00"

    mock_gpu = MagicMock()
    mock_gpu.findtext.side_effect = lambda x: {"product_name": "RTX 3080"}.get(x)
    mock_root.findall.return_value = [mock_gpu]
    mock_et.fromstring.return_value = mock_root

    result = get_nvidia_smi()
    assert result[0]["BAR1 Used (MiB)"] == 0
    assert result[0]["PCIe Max Width"] is None
    assert result[0]["PCIe Current Width"] is None
    assert result[0]["ReBAR"] is False


@patch("src.collectors.spec_dumper.get_nvidia_smi", side_effect=FileNotFoundError("nvidia-smi not found"))
@patch("src.collectors.spec_dumper.get_wmi_specs", return_value={"cpu": "Intel i9"})
@patch("src.collectors.spec_dumper.get_dxdiag", return_value={})
@patch("src.collectors.spec_dumper.get_amd_smi", return_value=[])
@patch("src.collectors.spec_dumper.get_lhm_data", return_value={})
@patch("src.collectors.spec_dumper.get_monitor_refresh_capabilities", return_value=[])
@patch("src.collectors.spec_dumper.get_active_power_plan", return_value=("guid-abc", "High Performance"))
@patch("src.collectors.spec_dumper.get_game_mode_status", return_value=True)
@patch("src.collectors.spec_dumper.get_temp_sizes", return_value={"total_bytes": 0, "details": {}})
def test_dump_system_specs_partial_failure(
    mock_temps, mock_gms, mock_pp, mock_mon, mock_lhm, mock_amd, mock_dx, mock_wmi, mock_nv, tmp_path
):
    output_file = str(tmp_path / "specs.json")
    result = dump_system_specs(output_file)
    assert result == output_file
    with open(output_file, "r") as f:
        data = json.load(f)
    assert "error" in data["NVIDIA"]
    assert data["WMI"] == {"cpu": "Intel i9"}


@patch("src.collectors.spec_dumper.get_wmi_specs", return_value={})
@patch("src.collectors.spec_dumper.get_dxdiag", return_value={})
@patch("src.collectors.spec_dumper.get_nvidia_smi", return_value=[])
@patch("src.collectors.spec_dumper.get_amd_smi", return_value=[])
@patch("src.collectors.spec_dumper.get_lhm_data", return_value={})
@patch("src.collectors.spec_dumper.get_monitor_refresh_capabilities", return_value=[])
@patch("src.collectors.spec_dumper.get_active_power_plan", return_value=("guid-abc", "High Performance"))
@patch("src.collectors.spec_dumper.get_game_mode_status", return_value=True)
@patch("src.collectors.spec_dumper.get_temp_sizes", return_value={"total_bytes": 0, "details": {}})
def test_dump_system_specs_writes_json(
    mock_temps, mock_gms, mock_pp, mock_mon, mock_lhm, mock_amd, mock_nv, mock_dx, mock_wmi, tmp_path
):
    output_file = str(tmp_path / "specs.json")
    result = dump_system_specs(output_file)
    assert result == output_file
    with open(output_file, "r") as f:
        data = json.load(f)
    assert "WMI" in data
    assert "NVIDIA" in data
    assert "CollectionTime" in data
