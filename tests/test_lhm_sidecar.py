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
def test_find_lhm_returns_custom_server(mock_isfile):
    """lhm-server.exe found → returns (path, True)."""
    mock_isfile.side_effect = lambda p: p.endswith("lhm-server.exe")
    path, is_custom = find_lhm_executable()
    assert path is not None
    assert path.endswith("lhm-server.exe")
    assert is_custom is True


@patch("src.collectors.sub.lhm_sidecar.os.path.isfile")
def test_find_lhm_returns_full_lhm(mock_isfile):
    """Only full LHM found → returns (path, False)."""
    mock_isfile.side_effect = lambda p: "LibreHardwareMonitor.exe" in p and "lhm-server" not in p
    path, is_custom = find_lhm_executable()
    assert path is not None
    assert "LibreHardwareMonitor.exe" in path
    assert is_custom is False


@patch("src.collectors.sub.lhm_sidecar.os.path.isfile", return_value=False)
def test_find_lhm_exe_not_found(mock_isfile):
    """Nothing found → returns (None, False)."""
    path, is_custom = find_lhm_executable()
    assert path is None
    assert is_custom is False


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

@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value=(None, False))
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_exe_not_found(mock_port, mock_find):
    sidecar = LHMSidecar()
    assert sidecar.start() is False


# ── LHMSidecar.start — successful launch (full LHM) ──────────────────────────

@patch("src.collectors.sub.lhm_sidecar.time.sleep")
@patch("src.collectors.sub.lhm_sidecar.time.monotonic")
@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding")
@patch("src.collectors.sub.lhm_sidecar.subprocess.Popen")
@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value=(r"C:\LHM\LibreHardwareMonitor.exe", False))
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_launches_full_lhm_successfully(mock_port, mock_find, mock_popen, mock_resp, mock_mono, mock_sleep):
    mock_proc = MagicMock()
    mock_proc.pid = 12345
    mock_popen.return_value = mock_proc

    mock_mono.side_effect = [0.0, 0.5, 1.0]
    mock_resp.side_effect = [False, True]

    sidecar = LHMSidecar()
    assert sidecar.start() is True
    assert sidecar._process is not None
    # Full LHM must be launched with --http-port flag
    call_args = mock_popen.call_args[0][0]
    assert "--http-port" in call_args
    assert str(LHM_PORT) in call_args


# ── LHMSidecar.start — custom server launches without --http-port ─────────────

@patch("src.collectors.sub.lhm_sidecar.time.sleep")
@patch("src.collectors.sub.lhm_sidecar.time.monotonic")
@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding")
@patch("src.collectors.sub.lhm_sidecar.subprocess.Popen")
@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value=(r"C:\tools\lhm-server.exe", True))
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_launches_custom_server_no_port_flag(mock_port, mock_find, mock_popen, mock_resp, mock_mono, mock_sleep):
    """lhm-server.exe has port hardcoded — must NOT receive --http-port arg."""
    mock_proc = MagicMock()
    mock_proc.pid = 99
    mock_popen.return_value = mock_proc

    mock_mono.side_effect = [0.0, 0.5, 1.0]
    mock_resp.side_effect = [False, True]

    sidecar = LHMSidecar()
    assert sidecar.start() is True
    call_args = mock_popen.call_args[0][0]
    assert "--http-port" not in call_args
    assert call_args == [r"C:\tools\lhm-server.exe"]


# ── LHMSidecar.start — launch timeout ────────────────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.time.sleep")
@patch("src.collectors.sub.lhm_sidecar.time.monotonic")
@patch("src.collectors.sub.lhm_sidecar._is_lhm_responding", return_value=False)
@patch("src.collectors.sub.lhm_sidecar.subprocess.Popen")
@patch("src.collectors.sub.lhm_sidecar.find_lhm_executable", return_value=(r"C:\LHM\LibreHardwareMonitor.exe", False))
@patch("src.collectors.sub.lhm_sidecar._is_port_in_use", return_value=False)
def test_start_launch_timeout(mock_port, mock_find, mock_popen, mock_resp, mock_mono, mock_sleep):
    mock_proc = MagicMock()
    mock_popen.return_value = mock_proc

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


# ── LHMSidecar._kill_process — taskkill fallback ──────────────────────────────

@patch("src.collectors.sub.lhm_sidecar.subprocess.run")
def test_kill_process_taskkill_fallback_on_terminate_failure(mock_run):
    """If terminate() times out, taskkill /F /T /PID is invoked as fallback."""
    import subprocess as _sp
    sidecar = LHMSidecar()
    mock_proc = MagicMock()
    mock_proc.pid = 1234
    mock_proc.terminate.return_value = None
    mock_proc.wait.side_effect = _sp.TimeoutExpired(cmd="lhm-server.exe", timeout=3)
    mock_proc.kill.side_effect = OSError("access denied")
    sidecar._process = mock_proc
    sidecar._already_running = False

    sidecar._kill_process()

    # taskkill must have been called with /F /T /PID {pid}
    mock_run.assert_called_once()
    call_args = mock_run.call_args[0][0]
    assert "taskkill" in call_args
    assert "/F" in call_args
    assert "/T" in call_args
    assert str(mock_proc.pid) in call_args


@patch("src.collectors.sub.lhm_sidecar.subprocess.run")
def test_kill_process_no_taskkill_on_clean_terminate(mock_run):
    """If terminate() + wait() succeed, taskkill is NOT invoked."""
    sidecar = LHMSidecar()
    mock_proc = MagicMock()
    mock_proc.pid = 5678
    sidecar._process = mock_proc
    sidecar._already_running = False

    sidecar._kill_process()

    mock_run.assert_not_called()


def test_kill_process_clears_process_ref():
    """_kill_process always sets self._process = None."""
    sidecar = LHMSidecar()
    sidecar._process = MagicMock()
    sidecar._already_running = False

    sidecar._kill_process()

    assert sidecar._process is None


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
