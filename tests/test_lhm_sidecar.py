import json
import pytest
from unittest.mock import patch, MagicMock

from src.collectors.sub.lhm_sidecar import (
    LHMSidecar,
    _is_port_in_use,
    _is_lhm_responding,
    find_lhm_executable,
    LHM_PORT,
)


# ── Port probe tests ─────────────────────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.socket.socket")
def test_port_in_use_returns_true(mock_socket_cls):
    mock_sock = MagicMock()
    mock_sock.connect_ex.return_value = 0
    mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
    mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
    assert _is_port_in_use(8085) is True


@patch("src.collectors.sub.lhm_sidecar.socket.socket")
def test_port_not_in_use_returns_false(mock_socket_cls):
    mock_sock = MagicMock()
    mock_sock.connect_ex.return_value = 1
    mock_socket_cls.return_value.__enter__ = MagicMock(return_value=mock_sock)
    mock_socket_cls.return_value.__exit__ = MagicMock(return_value=False)
    assert _is_port_in_use(8085) is False


# ── LHM responding tests ─────────────────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.urllib.request.urlopen")
def test_lhm_responding_valid_json(mock_urlopen):
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps({"Children": []}).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp
    assert _is_lhm_responding() is True


@patch("src.collectors.sub.lhm_sidecar.urllib.request.urlopen", side_effect=Exception("timeout"))
def test_lhm_not_responding(mock_urlopen):
    assert _is_lhm_responding() is False


# ── find_lhm_executable ──────────────────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.os.path.isfile")
def test_find_lhm_exe_found(mock_isfile):
    # First path checked returns True
    mock_isfile.side_effect = lambda p: "tools" in p
    result = find_lhm_executable()
    assert result is not None
    assert "LibreHardwareMonitor.exe" in result


@patch("src.collectors.sub.lhm_sidecar.os.path.isfile", return_value=False)
def test_find_lhm_exe_not_found(mock_isfile):
    assert find_lhm_executable() is None


# ── LHMSidecar.start — already running ───────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding", return_value=True)
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=True)
def test_start_attaches_to_existing(mock_port, mock_resp):
    sidecar = LHMSidecar()
    assert sidecar.start() is True
    assert sidecar._already_running is True


# ── LHMSidecar.start — port occupied by other app ────────────────────────────

@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding", return_value=False)
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=True)
def test_start_port_occupied_by_other(mock_port, mock_resp):
    sidecar = LHMSidecar()
    assert sidecar.start() is False


# ── LHMSidecar.start — exe not found ─────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value=None)
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_exe_not_found(mock_port, mock_find):
    sidecar = LHMSidecar()
    assert sidecar.start() is False


# ── LHMSidecar.start — successful launch ─────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.time.sleep")
@patch("src.collectors.sub.lhm_sidecar.time.monotonic")
@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding")
@patch("src.collectors.sub.lhm_sidecar.subprocess.Popen")
@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value="C:\\LHM\\LHM.exe")
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_launches_successfully(mock_port, mock_find, mock_popen, mock_resp, mock_mono, mock_sleep):
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_popen.return_value = mock_proc

    # First call to monotonic for deadline, then respond ready on second check
    mock_mono.side_effect = [0.0, 0.5, 1.0]
    mock_resp.side_effect = [False, True]

    sidecar = LHMSidecar()
    assert sidecar.start() is True
    assert sidecar._process is not None


# ── LHMSidecar.start — launch timeout ────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.time.sleep")
@patch("src.collectors.sub.lhm_sidecar.time.monotonic")
@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding", return_value=False)
@patch("src.collectors.sub.lhm_sidecar.subprocess.Popen")
@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value="C:\\LHM\\LHM.exe")
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_launch_timeout(mock_port, mock_find, mock_popen, mock_resp, mock_mono, mock_sleep):
    mock_proc = MagicMock()
    mock_popen.return_value = mock_proc

    # Monotonic returns values past the deadline immediately
    mock_mono.side_effect = [0.0, 6.0]

    sidecar = LHMSidecar()
    assert sidecar.start() is False
    mock_proc.terminate.assert_called_once()


# ── LHMSidecar.stop — doesn't kill external instance ─────────────────────────

def test_stop_skips_external_instance():
    sidecar = LHMSidecar()
    sidecar._already_running = True
    sidecar._process = MagicMock()
    sidecar.stop()
    # Should NOT terminate since we didn't start it
    sidecar._process.terminate.assert_not_called()


# ── LHMSidecar.stop — kills our process ──────────────────────────────────────

def test_stop_terminates_our_process():
    sidecar = LHMSidecar()
    sidecar._already_running = False
    mock_proc = MagicMock()
    sidecar._process = mock_proc
    sidecar.stop()
    mock_proc.terminate.assert_called_once()


# ── LHMSidecar.fetch_data ────────────────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.urllib.request.urlopen")
def test_fetch_data_success(mock_urlopen):
    test_data = {"Children": [{"Text": "CPU"}]}
    mock_resp = MagicMock()
    mock_resp.read.return_value = json.dumps(test_data).encode()
    mock_resp.__enter__ = MagicMock(return_value=mock_resp)
    mock_resp.__exit__ = MagicMock(return_value=False)
    mock_urlopen.return_value = mock_resp

    sidecar = LHMSidecar()
    result = sidecar.fetch_data()
    assert result == test_data


@patch("src.collectors.sub.lhm_sidecar.urllib.request.urlopen", side_effect=Exception("fail"))
def test_fetch_data_failure(mock_urlopen):
    sidecar = LHMSidecar()
    assert sidecar.fetch_data() is None
