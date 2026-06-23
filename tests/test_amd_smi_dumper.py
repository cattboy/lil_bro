"""Tests for src.collectors.sub.amd_smi_dumper.get_amd_smi.

get_amd_smi() does `import amdsmi` *inside* the function body, so the amdsmi
library cannot be patched with ``unittest.mock.patch`` on a module attribute
(it isn't bound at import time). Instead we inject a fake ``amdsmi`` module into
``sys.modules`` for the success path, and remove it (forcing ImportError) for
the CLI-fallback path. The CLI fallback calls ``run_subprocess``, imported at
module scope, so it's patched at the dumper's call site.
"""

import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.sub.amd_smi_dumper import get_amd_smi


def _fake_amdsmi(*, devices, board=None, vram=None, driver=None):
    """Build a fake ``amdsmi`` module object whose getters return the dicts given."""
    mod = MagicMock(name="amdsmi")
    mod.amdsmi_init.return_value = None
    mod.amdsmi_shut_down.return_value = None
    mod.amdsmi_get_processor_handles.return_value = devices
    mod.amdsmi_get_gpu_board_info.return_value = board if board is not None else {}
    mod.amdsmi_get_gpu_vram_info.return_value = vram if vram is not None else {}
    mod.amdsmi_get_gpu_driver_info.return_value = driver if driver is not None else {}
    return mod


def test_get_amd_smi_success_single_gpu():
    """Fake amdsmi with one device → list with parsed board/vram/driver fields."""
    fake = _fake_amdsmi(
        devices=["dev0"],
        board={"product_name": "Radeon RX 7900 XTX"},
        vram={"vram_size": 24576},
        driver={"driver_version": "23.40.27.06"},
    )
    with patch.dict(sys.modules, {"amdsmi": fake}):
        result = get_amd_smi()

    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["GPU"] == "Radeon RX 7900 XTX"
    assert result[0]["VRAM_MiB"] == 24576
    assert result[0]["Driver"] == "23.40.27.06"
    assert result[0]["ReBAR"] == "Unknown via amdsmi"
    fake.amdsmi_init.assert_called_once()
    fake.amdsmi_shut_down.assert_called_once()


def test_get_amd_smi_success_multi_gpu():
    """Two devices → two rows."""
    fake = _fake_amdsmi(
        devices=["dev0", "dev1"],
        board={"product_name": "Radeon RX 7800 XT"},
        vram={"vram_size": 16384},
        driver={"driver_version": "24.1.1"},
    )
    with patch.dict(sys.modules, {"amdsmi": fake}):
        result = get_amd_smi()

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(r["GPU"] == "Radeon RX 7800 XT" for r in result)


def test_get_amd_smi_per_field_exceptions_use_defaults():
    """Each getter raising → that field falls back to its default, no crash."""
    fake = MagicMock(name="amdsmi")
    fake.amdsmi_get_processor_handles.return_value = ["dev0"]
    fake.amdsmi_get_gpu_board_info.side_effect = RuntimeError("board boom")
    fake.amdsmi_get_gpu_vram_info.side_effect = RuntimeError("vram boom")
    fake.amdsmi_get_gpu_driver_info.side_effect = RuntimeError("driver boom")
    with patch.dict(sys.modules, {"amdsmi": fake}):
        result = get_amd_smi()

    assert isinstance(result, list)
    assert result[0]["GPU"] == "Unknown AMD GPU"
    assert result[0]["VRAM_MiB"] == 0
    assert result[0]["Driver"] == "Unknown"


def test_get_amd_smi_no_devices_returns_message():
    """Empty device list → human-readable 'no GPUs' string, not an empty list."""
    fake = _fake_amdsmi(devices=[])
    with patch.dict(sys.modules, {"amdsmi": fake}):
        result = get_amd_smi()

    assert result == "No AMD GPUs found via amdsmi"


def test_get_amd_smi_init_raises_returns_library_exception_string():
    """amdsmi_init raising → 'amdsmi library exception: ...' string."""
    fake = MagicMock(name="amdsmi")
    fake.amdsmi_init.side_effect = RuntimeError("driver not loaded")
    with patch.dict(sys.modules, {"amdsmi": fake}):
        result = get_amd_smi()

    assert isinstance(result, str)
    assert result.startswith("amdsmi library exception:")
    assert "driver not loaded" in result


def test_get_amd_smi_no_library_cli_succeeds():
    """No amdsmi module → CLI fallback; rc==0 → 'requires parsing implementation'."""
    with patch.dict(sys.modules, {"amdsmi": None}), patch(
        "src.collectors.sub.amd_smi_dumper.run_subprocess",
        return_value=SimpleNamespace(returncode=0, stdout="static info"),
    ) as mock_run:
        result = get_amd_smi()

    assert result == "amd-smi CLI found but requires parsing implementation"
    mock_run.assert_called_once_with(["amd-smi", "static"])


def test_get_amd_smi_no_library_cli_nonzero_rc():
    """No amdsmi module, CLI returns non-zero → 'module not installed and CLI failed'."""
    with patch.dict(sys.modules, {"amdsmi": None}), patch(
        "src.collectors.sub.amd_smi_dumper.run_subprocess",
        return_value=SimpleNamespace(returncode=1, stdout=""),
    ):
        result = get_amd_smi()

    assert result == "amdsmi Python module not installed and CLI failed"


@pytest.mark.parametrize(
    "exc",
    [FileNotFoundError("amd-smi missing"), subprocess.TimeoutExpired(cmd="amd-smi", timeout=5)],
)
def test_get_amd_smi_no_library_cli_not_found(exc):
    """No amdsmi module + CLI missing/timeout → 'module not installed and CLI not found'."""
    with patch.dict(sys.modules, {"amdsmi": None}), patch(
        "src.collectors.sub.amd_smi_dumper.run_subprocess", side_effect=exc
    ):
        result = get_amd_smi()

    assert result == "amdsmi Python module not installed and CLI not found"
