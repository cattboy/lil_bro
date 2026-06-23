"""Tests for src.collectors.sub.libra_hm_dumper.get_lhm_data.

get_lhm_data() GETs LHM's /data.json (2 s timeout) and json.loads the body,
returning the parsed object on success or an error *string* on any failure.
urlopen is patched at this module's call site so no real HTTP happens.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.sub.libra_hm_dumper import get_lhm_data
from src.collectors.sub.lhm_sidecar import LHM_URL


def _mock_response(payload_bytes):
    """A urlopen context-manager mock whose .read() yields the given bytes."""
    resp = MagicMock()
    resp.read.return_value = payload_bytes
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_get_lhm_data_success_returns_parsed_dict():
    """Valid JSON sensor tree → returns the parsed dict unchanged."""
    tree = {"Children": [{"Text": "CPU", "Value": "55.0 °C"}]}
    resp = _mock_response(json.dumps(tree).encode())
    with patch("src.collectors.sub.libra_hm_dumper.urllib.request.urlopen", return_value=resp):
        result = get_lhm_data()

    assert result == tree


def test_get_lhm_data_success_uses_lhm_url():
    """The request targets LHM_URL (single source of truth from lhm_sidecar)."""
    resp = _mock_response(json.dumps({"Children": []}).encode())
    with patch("src.collectors.sub.libra_hm_dumper.urllib.request.urlopen", return_value=resp), \
         patch("src.collectors.sub.libra_hm_dumper.urllib.request.Request") as mock_req:
        get_lhm_data()

    mock_req.assert_called_once_with(LHM_URL)


def test_get_lhm_data_connection_error_returns_string():
    """urlopen raising (LHM down) → human-readable error string, not an exception."""
    with patch(
        "src.collectors.sub.libra_hm_dumper.urllib.request.urlopen",
        side_effect=OSError("connection refused"),
    ):
        result = get_lhm_data()

    assert isinstance(result, str)
    assert "not reachable" in result
    assert "connection refused" in result


def test_get_lhm_data_invalid_json_returns_string():
    """Body that isn't JSON → json.loads raises → caught and returned as a string."""
    resp = _mock_response(b"<html>not json</html>")
    with patch("src.collectors.sub.libra_hm_dumper.urllib.request.urlopen", return_value=resp):
        result = get_lhm_data()

    assert isinstance(result, str)
    assert "not reachable" in result


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timed out"),
        OSError("port closed"),
        ValueError("bad value"),
    ],
)
def test_get_lhm_data_various_failures_return_string(exc):
    """Any exception in the fetch path is swallowed into the error string."""
    with patch(
        "src.collectors.sub.libra_hm_dumper.urllib.request.urlopen", side_effect=exc
    ):
        result = get_lhm_data()

    assert isinstance(result, str)
    assert "not reachable" in result
