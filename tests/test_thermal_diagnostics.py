"""Tests for thermal sidecar failure attribution (feat/prereq-check).

Covers the pure classifier (classify_sidecar_failure), the .NET-host-error guard,
the never-raise describe_sidecar_failure wrapper, and the _port_owner probe.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.agent_tools.thermal_guidance import (
    classify_sidecar_failure,
    describe_sidecar_failure,
    _is_dotnet_host_error,
)
from src.collectors.sub.lhm_process_utils import _port_owner


# ── classify_sidecar_failure: every kind yields a WARNING + actionable text ────

@pytest.mark.parametrize("kind", [
    "port_in_use", "not_found", "elevation_failed", "launch_error",
    "exited_immediately", "timeout", "no_sensors", "unknown", "brand-new-kind",
])
def test_classify_returns_warning_and_nonempty_message(kind):
    result = classify_sidecar_failure(kind, {})
    assert result["status"] == "WARNING"
    assert isinstance(result["message"], str) and result["message"].strip()


def test_classify_port_in_use_names_owner():
    msg = classify_sidecar_failure("port_in_use", {"port_owner": "OtherApp.exe"})["message"]
    assert "8085" in msg
    assert "OtherApp.exe" in msg


def test_classify_port_in_use_without_owner_is_generic():
    msg = classify_sidecar_failure("port_in_use", {"port_owner": None})["message"]
    assert "8085" in msg
    assert "another application" in msg


def test_classify_not_found_mentions_reinstall():
    msg = classify_sidecar_failure("not_found", {})["message"].lower()
    assert "missing" in msg or "reinstall" in msg


def test_classify_launch_error_mentions_antivirus():
    msg = classify_sidecar_failure("launch_error", {})["message"].lower()
    assert "antivirus" in msg


def test_classify_exited_immediately_av_vs_dotnet():
    av = classify_sidecar_failure("exited_immediately", {}, returncode=1)["message"].lower()
    assert "antivirus" in av
    dotnet = classify_sidecar_failure(
        "exited_immediately", {}, returncode=0x80008096
    )["message"].lower()
    assert "runtime" in dotnet


def test_classify_timeout_pawnio_aware():
    no_pawnio = classify_sidecar_failure("timeout", {"pawnio_installed": False})["message"]
    assert "PawnIO" in no_pawnio
    with_pawnio = classify_sidecar_failure("timeout", {"pawnio_installed": True})["message"].lower()
    assert "respond" in with_pawnio


def test_classify_no_sensors_pawnio_aware():
    blocked = classify_sidecar_failure("no_sensors", {"pawnio_installed": False})["message"]
    assert "PawnIO" in blocked or "Secure Boot" in blocked
    running = classify_sidecar_failure("no_sensors", {"pawnio_installed": True})["message"].lower()
    assert "no cpu sensors" in running


def test_classify_unknown_is_catch_all():
    msg = classify_sidecar_failure("something-new", {})["message"].lower()
    assert "unavailable" in msg


def test_classify_tolerates_none_probes():
    # Pure fn must not assume probes is a dict.
    assert classify_sidecar_failure("port_in_use", None)["message"]


# ── _is_dotnet_host_error ─────────────────────────────────────────────────────

def test_dotnet_host_error_by_returncode():
    assert _is_dotnet_host_error(0x80008096, None) is True
    assert _is_dotnet_host_error(-2147450730, None) is True


def test_dotnet_host_error_by_stderr():
    assert _is_dotnet_host_error(None, ["FATAL: hostfxr not found"]) is True
    assert _is_dotnet_host_error(None, ["You must install the .NET runtime"]) is True


def test_dotnet_host_error_false_for_benign():
    assert _is_dotnet_host_error(1, ["PawnIO install failed"]) is False
    assert _is_dotnet_host_error(None, []) is False
    assert _is_dotnet_host_error(None, None) is False


# ── describe_sidecar_failure: reads the instance, never raises ────────────────

def _fake_lhm(kind=None, returncode=None, stderr=None):
    lhm = MagicMock()
    lhm.last_failure_kind = kind
    lhm.last_returncode = returncode
    lhm.last_stderr_lines = stderr
    return lhm


@patch("src.agent_tools.thermal_guidance._gather_sidecar_probes",
       return_value={"pawnio_installed": True})
def test_describe_uses_instance_kind(mock_probes):
    msg = describe_sidecar_failure(_fake_lhm(kind="not_found"))
    assert "missing" in msg.lower() or "reinstall" in msg.lower()


@patch("src.agent_tools.thermal_guidance._gather_sidecar_probes",
       return_value={"pawnio_installed": False})
def test_describe_no_sensors_flag_overrides_kind(mock_probes):
    msg = describe_sidecar_failure(_fake_lhm(kind=None), no_sensors=True)
    assert "PawnIO" in msg or "Secure Boot" in msg


@patch("src.agent_tools.thermal_guidance._gather_sidecar_probes", return_value={})
def test_describe_missing_kind_falls_back_to_unknown(mock_probes):
    msg = describe_sidecar_failure(_fake_lhm(kind=None))
    assert "unavailable" in msg.lower()


@patch("src.agent_tools.thermal_guidance._gather_sidecar_probes",
       side_effect=RuntimeError("probe blew up"))
def test_describe_never_raises_on_probe_failure(mock_probes):
    """describe runs on an already-failing path; a probe exception must not escape."""
    msg = describe_sidecar_failure(_fake_lhm(kind="port_in_use"))  # must not raise
    assert isinstance(msg, str) and msg.strip()


# ── _port_owner ───────────────────────────────────────────────────────────────

@patch("psutil.Process")
@patch("psutil.net_connections")
def test_port_owner_returns_process_name(mock_conns, mock_proc):
    conn = MagicMock()
    conn.laddr.port = 8085
    conn.pid = 4321
    mock_conns.return_value = [conn]
    mock_proc.return_value.name.return_value = "Greedy.exe"
    assert _port_owner(8085) == "Greedy.exe"


@patch("psutil.net_connections", return_value=[])
def test_port_owner_none_when_no_match(mock_conns):
    assert _port_owner(8085) is None


@patch("psutil.net_connections", side_effect=PermissionError("AccessDenied"))
def test_port_owner_none_on_access_denied(mock_conns):
    assert _port_owner(8085) is None


# ── thermal_gate surfaces the cause (consumer) ────────────────────────────────

def test_require_thermal_protection_surfaces_cause(capsys):
    """LHM unavailable → gate skips AND names the specific cause (not generic)."""
    from types import SimpleNamespace
    from src.pipeline.thermal_gate import require_thermal_protection
    fake_lhm = SimpleNamespace(last_failure_kind="port_in_use",
                               last_returncode=None, last_stderr_lines=None)
    ctx = SimpleNamespace(lhm_available=False, lhm=fake_lhm)
    with patch("src.agent_tools.thermal_guidance._gather_sidecar_probes",
               return_value={"port_owner": "Hog.exe", "pawnio_installed": True}):
        skipped = require_thermal_protection("Baseline", ctx)
    out = capsys.readouterr().out
    assert skipped is True
    assert "Hog.exe" in out or "8085" in out


def test_require_thermal_protection_no_sensors_branch(capsys):
    """LHM up but empty snapshot → gate skips and attributes the PawnIO cause."""
    from types import SimpleNamespace
    from src.pipeline.thermal_gate import require_thermal_protection
    fake_lhm = SimpleNamespace(last_failure_kind=None,
                               last_returncode=None, last_stderr_lines=None)
    ctx = SimpleNamespace(lhm_available=True, lhm=fake_lhm)
    with patch("src.agent_tools.thermal_guidance._gather_sidecar_probes",
               return_value={"pawnio_installed": False}), \
         patch("src.pipeline.thermal_gate.fetch_snapshot", return_value={}):
        skipped = require_thermal_protection("Final", ctx)
    out = capsys.readouterr().out
    assert skipped is True
    assert "PawnIO" in out or "Secure Boot" in out


# ── _ThermalRetryWorker (Dashboard Retry) ─────────────────────────────────────

def test_thermal_retry_worker_success():
    """Retry: stops the old sidecar, starts a fresh one, reports available."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.worker import _ThermalRetryWorker
    old = MagicMock()
    with patch("src.collectors.sub.lhm_sidecar.LHMSidecar") as MockLHM:
        new = MagicMock()
        new.start.return_value = True
        MockLHM.return_value = new
        w = _ThermalRetryWorker(old)
        w.run()
    old.stop.assert_called_once()
    assert w.available is True
    assert w.new_lhm is new
    assert w.reason == ""


def test_thermal_retry_worker_failure_sets_reason():
    """Retry that still fails → available False + classified reason set."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.worker import _ThermalRetryWorker
    with patch("src.collectors.sub.lhm_sidecar.LHMSidecar") as MockLHM, \
         patch("src.agent_tools.thermal_guidance._gather_sidecar_probes",
               return_value={"pawnio_installed": True}):
        new = MagicMock()
        new.start.return_value = False
        new.last_failure_kind = "launch_error"
        MockLHM.return_value = new
        w = _ThermalRetryWorker(None)  # no prior sidecar to stop
        w.run()
    assert w.available is False
    assert "antivirus" in w.reason.lower()


# ── thermal_chart paints a long wrapped offline message without error ─────────

def test_thermal_chart_offline_paints_long_message_without_error():
    """A long word-wrapped offline cause must paint without raising -- covers the
    AlignmentFlag|TextFlag combination in _paint_status (only hit on real paint)."""
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from src.gui.widgets.thermal_chart import ThermalChart
    chart = ThermalChart()
    chart.resize(220, 140)
    chart.set_offline(
        "Port 8085 is in use by Hog.exe. Close it and retry to restore thermal "
        "monitoring. Add an exclusion for lhm-server.exe if antivirus is the cause."
    )
    pixmap = chart.grab()  # forces paintEvent -> _paint_status
    assert not pixmap.isNull()
