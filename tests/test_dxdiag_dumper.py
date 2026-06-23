"""Tests for src.collectors.sub.dxdiag_dumper.get_dxdiag.

get_dxdiag() shells out to dxdiag.exe (Windows-only), then polls for the XML
report in a ``for _ in range(30): ... time.sleep(0.5)`` loop and ET.parses it.
We never spawn real dxdiag: subprocess.run, the os.path probes, ET.parse, and
time.sleep are all patched. The poll loop's time.sleep MUST be patched so the
timeout path doesn't actually block 15 s.
"""

import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.sub.dxdiag_dumper import get_dxdiag


_SAMPLE_DXDIAG_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DxDiag>
  <SystemInformation>
    <DirectXVersion>DirectX 12</DirectXVersion>
  </SystemInformation>
  <DisplayDevices>
    <DisplayDevice>
      <CardName>NVIDIA GeForce RTX 4090</CardName>
      <DisplayMemory>24576 MB</DisplayMemory>
    </DisplayDevice>
  </DisplayDevices>
  <DirectInput>
    <LogicalDisks>
      <LogicalDisk>
        <DriveLetter>C:</DriveLetter>
        <FreeSpace>500 GB</FreeSpace>
      </LogicalDisk>
    </LogicalDisks>
  </DirectInput>
</DxDiag>
"""


def test_get_dxdiag_raises_on_non_windows():
    """Outside Windows → RuntimeError before any subprocess is spawned."""
    with patch("src.collectors.sub.dxdiag_dumper.platform.system", return_value="Linux"):
        with pytest.raises(RuntimeError, match="only supported on Windows"):
            get_dxdiag()


def test_get_dxdiag_success_parses_xml():
    """File appears immediately + valid XML → parsed dict with expected sections."""
    real_root = ET.fromstring(_SAMPLE_DXDIAG_XML)
    mock_tree = MagicMock()
    mock_tree.getroot.return_value = real_root

    with patch("src.collectors.sub.dxdiag_dumper.platform.system", return_value="Windows"), \
         patch("src.collectors.sub.dxdiag_dumper.subprocess.run") as mock_run, \
         patch("src.collectors.sub.dxdiag_dumper.os.path.exists", return_value=True), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.getsize", return_value=4096), \
         patch("src.collectors.sub.dxdiag_dumper.ET.parse", return_value=mock_tree) as mock_parse, \
         patch("src.collectors.sub.dxdiag_dumper.time.sleep") as mock_sleep:
        result = get_dxdiag()

    assert result["DirectXVersion"] == "DirectX 12"
    assert result["DisplayDevices"] == [
        {"CardName": "NVIDIA GeForce RTX 4090", "DisplayMemory": "24576 MB"}
    ]
    assert result["LogicalDisks"] == [{"DriveLetter": "C:", "FreeSpace": "500 GB"}]
    mock_run.assert_called_once()
    mock_parse.assert_called_once()
    # File was ready on the first probe → loop never sleeps.
    mock_sleep.assert_not_called()


def test_get_dxdiag_waits_then_parses_when_file_late():
    """File missing on first probes, then appears → returns parsed dict; slept while waiting."""
    real_root = ET.fromstring(_SAMPLE_DXDIAG_XML)
    mock_tree = MagicMock()
    mock_tree.getroot.return_value = real_root
    # First two iterations: file absent. Third: present.
    exists_seq = iter([False, False, True])

    with patch("src.collectors.sub.dxdiag_dumper.platform.system", return_value="Windows"), \
         patch("src.collectors.sub.dxdiag_dumper.subprocess.run"), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.exists", side_effect=lambda p: next(exists_seq)), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.getsize", return_value=4096), \
         patch("src.collectors.sub.dxdiag_dumper.ET.parse", return_value=mock_tree), \
         patch("src.collectors.sub.dxdiag_dumper.time.sleep") as mock_sleep:
        result = get_dxdiag()

    assert result["DirectXVersion"] == "DirectX 12"
    # Slept on the two iterations where the file wasn't ready yet.
    assert mock_sleep.call_count == 2


def test_get_dxdiag_timeout_when_file_never_appears():
    """File never materialises across all 30 iterations → RuntimeError (timeout)."""
    with patch("src.collectors.sub.dxdiag_dumper.platform.system", return_value="Windows"), \
         patch("src.collectors.sub.dxdiag_dumper.subprocess.run"), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.exists", return_value=False), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.getsize", return_value=0), \
         patch("src.collectors.sub.dxdiag_dumper.ET.parse") as mock_parse, \
         patch("src.collectors.sub.dxdiag_dumper.time.sleep") as mock_sleep:
        with pytest.raises(RuntimeError, match="timed out"):
            get_dxdiag()

    # Never parsed (file never existed) and slept once per iteration.
    mock_parse.assert_not_called()
    assert mock_sleep.call_count == 30


def test_get_dxdiag_partial_write_then_complete():
    """File exists but is mid-write (ET.ParseError), then parses on a later poll."""
    real_root = ET.fromstring(_SAMPLE_DXDIAG_XML)
    good_tree = MagicMock()
    good_tree.getroot.return_value = real_root
    # First parse: file still being written → ParseError. Second: success.
    parse_seq = iter([ET.ParseError("not well-formed"), good_tree])

    def fake_parse(_path):
        outcome = next(parse_seq)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    with patch("src.collectors.sub.dxdiag_dumper.platform.system", return_value="Windows"), \
         patch("src.collectors.sub.dxdiag_dumper.subprocess.run"), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.exists", return_value=True), \
         patch("src.collectors.sub.dxdiag_dumper.os.path.getsize", return_value=4096), \
         patch("src.collectors.sub.dxdiag_dumper.ET.parse", side_effect=fake_parse), \
         patch("src.collectors.sub.dxdiag_dumper.time.sleep") as mock_sleep:
        result = get_dxdiag()

    assert result["DirectXVersion"] == "DirectX 12"
    # ParseError on the first poll → slept once before the successful re-parse.
    assert mock_sleep.call_count == 1
