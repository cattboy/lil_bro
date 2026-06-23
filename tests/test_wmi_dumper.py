"""Tests for src.collectors.sub.wmi_dumper.

The module guards ``import wmi`` with ``try/except → wmi = None``. get_wmi_specs()
returns an ``{"error": ...}`` dict when wmi is unavailable, a populated specs dict
on success, and an ``{"error": "WMI query failed: ..."}`` dict when a query raises.
We patch the module-level ``wmi`` attribute rather than spawning real WMI.
_check_rebar_wmi(c) is exercised directly with fake Win32_DeviceMemoryAddress rows.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.collectors.sub.wmi_dumper import _check_rebar_wmi, get_wmi_specs


def _make_wmi_connection():
    """A fake ``wmi.WMI()`` connection returning one of each Win32_* class."""
    c = MagicMock()

    os_obj = MagicMock(Caption="Windows 11 Pro", Version="10.0.26200")
    cpu = MagicMock(Name="AMD Ryzen 9 7950X", NumberOfCores=16, MaxClockSpeed=4500)
    ram = MagicMock(Capacity="34359738368", Speed=6000, ConfiguredClockSpeed=6000)
    mobo = MagicMock(Manufacturer="ASUS", Product="ROG STRIX X670E")
    bios = MagicMock(SMBIOSBIOSVersion="2.10")
    video = MagicMock(Name="NVIDIA GeForce RTX 4090", AdapterRAM=4293918720, CurrentRefreshRate=144)
    disk = MagicMock(Model="Samsung 990 PRO", Size="2000398934016")
    # ReBAR probe: one large window (>256 MB) → enabled.
    mem = MagicMock(StartingAddress="0", EndingAddress=str(8 * 1024 * 1024 * 1024 - 1))

    c.Win32_OperatingSystem.return_value = [os_obj]
    c.Win32_Processor.return_value = [cpu]
    c.Win32_PhysicalMemory.return_value = [ram]
    c.Win32_BaseBoard.return_value = [mobo]
    c.Win32_BIOS.return_value = [bios]
    c.Win32_VideoController.return_value = [video]
    c.Win32_DiskDrive.return_value = [disk]
    c.Win32_DeviceMemoryAddress.return_value = [mem]
    return c


# ── get_wmi_specs: module unavailable ────────────────────────────────────────


def test_get_wmi_specs_module_unavailable():
    """wmi is None (import failed / non-Windows) → error dict, no crash."""
    with patch("src.collectors.sub.wmi_dumper.wmi", None):
        result = get_wmi_specs()

    assert result == {"error": "WMI module not installed or unsupported OS"}


# ── get_wmi_specs: success ───────────────────────────────────────────────────


def test_get_wmi_specs_success_populates_all_sections():
    """Fake WMI connection → fully populated specs dict."""
    fake_wmi = MagicMock()
    fake_wmi.WMI.return_value = _make_wmi_connection()
    with patch("src.collectors.sub.wmi_dumper.wmi", fake_wmi):
        result = get_wmi_specs()

    assert "error" not in result
    assert result["OS"] == [{"Name": "Windows 11 Pro", "Version": "10.0.26200"}]
    assert result["CPU"][0]["Name"] == "AMD Ryzen 9 7950X"
    assert result["CPU"][0]["Cores"] == 16
    assert result["RAM"][0]["Capacity_GB"] == 34.4  # 34359738368 / 1e9 rounded
    assert result["Motherboard"] == [{"Make": "ASUS", "Model": "ROG STRIX X670E"}]
    assert result["BIOS"] == [{"Version": "2.10"}]
    assert result["VideoController"][0]["Name"] == "NVIDIA GeForce RTX 4090"
    assert result["DiskDrive"][0]["Model"] == "Samsung 990 PRO"
    assert result["ReBAR"]["enabled"] is True


def test_get_wmi_specs_query_failure_returns_error():
    """A WMI query raising → {'error': 'WMI query failed: ...'} dict."""
    fake_wmi = MagicMock()
    fake_wmi.WMI.side_effect = RuntimeError("RPC server unavailable")
    with patch("src.collectors.sub.wmi_dumper.wmi", fake_wmi):
        result = get_wmi_specs()

    assert "error" in result
    assert result["error"].startswith("WMI query failed:")
    assert "RPC server unavailable" in result["error"]


# ── _check_rebar_wmi ─────────────────────────────────────────────────────────


def test_check_rebar_enabled_large_window():
    """A memory window larger than 256 MB → ReBAR enabled with the window size."""
    c = MagicMock()
    big = MagicMock(StartingAddress="0", EndingAddress=str(8 * 1024 * 1024 * 1024 - 1))
    c.Win32_DeviceMemoryAddress.return_value = [big]
    result = _check_rebar_wmi(c)
    assert result["enabled"] is True
    assert result["max_range_mb"] == pytest.approx(8192.0)


def test_check_rebar_disabled_only_small_windows():
    """All windows ≤ 256 MB → ReBAR disabled."""
    c = MagicMock()
    small = MagicMock(StartingAddress="0", EndingAddress=str(64 * 1024 * 1024 - 1))  # 64 MB
    c.Win32_DeviceMemoryAddress.return_value = [small]
    result = _check_rebar_wmi(c)
    assert result == {"enabled": False, "max_range_mb": 0.0}


def test_check_rebar_skips_unparseable_rows():
    """Rows with non-numeric addresses are skipped; a valid large one still wins."""
    c = MagicMock()
    bad = MagicMock(StartingAddress="N/A", EndingAddress="N/A")
    good = MagicMock(StartingAddress="0", EndingAddress=str(512 * 1024 * 1024 - 1))  # 512 MB
    c.Win32_DeviceMemoryAddress.return_value = [bad, good]
    result = _check_rebar_wmi(c)
    assert result["enabled"] is True
    assert result["max_range_mb"] == pytest.approx(512.0)
