"""Tests for src.collectors.sub.lhm_http.

_is_lhm_responding() is the cheapest LHM health check: a 2 s GET against LHM_URL
that confirms the body is a JSON object (dict). A capped read guards against an
attacker-controlled body on port 8085. urlopen is patched at this module's call
site; nothing real is fetched.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.collectors.sub.lhm_http import (
    LHM_PORT,
    LHM_URL,
    _MAX_RESPONSE_BYTES,
    _is_lhm_responding,
)


def _mock_response(payload_bytes):
    """A urlopen context-manager mock whose .read(n) yields the given bytes."""
    resp = MagicMock()
    resp.read.return_value = payload_bytes
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ── Module constants ─────────────────────────────────────────────────────────


def test_constants():
    """Port/URL constants are the well-known LHM defaults."""
    assert LHM_PORT == 8085
    assert LHM_URL == "http://localhost:8085/data.json"
    assert _MAX_RESPONSE_BYTES == 10 * 1024 * 1024


# ── _is_lhm_responding ───────────────────────────────────────────────────────


def test_responding_valid_json_object():
    """Top-level JSON object → True (LHM returns a dict with a 'Children' key)."""
    resp = _mock_response(json.dumps({"Children": [], "Text": "Sensor"}).encode())
    with patch("src.collectors.sub.lhm_http.urllib.request.urlopen", return_value=resp):
        assert _is_lhm_responding() is True


def test_responding_targets_lhm_url():
    """The probe request is built against LHM_URL."""
    resp = _mock_response(json.dumps({"Children": []}).encode())
    with patch("src.collectors.sub.lhm_http.urllib.request.urlopen", return_value=resp), \
         patch("src.collectors.sub.lhm_http.urllib.request.Request") as mock_req:
        _is_lhm_responding()

    mock_req.assert_called_once_with(LHM_URL)


@pytest.mark.parametrize(
    "payload",
    [
        json.dumps([1, 2, 3]).encode(),  # JSON array, not object
        json.dumps("a string").encode(),  # JSON string
        json.dumps(42).encode(),  # JSON number
    ],
)
def test_responding_non_dict_json_is_false(payload):
    """Valid JSON that isn't a dict → False (some other service owns the port)."""
    resp = _mock_response(payload)
    with patch("src.collectors.sub.lhm_http.urllib.request.urlopen", return_value=resp):
        assert _is_lhm_responding() is False


def test_responding_invalid_json_is_false():
    """Body that isn't JSON at all → False (json.loads raises, caught)."""
    resp = _mock_response(b"<html>503 Service Unavailable</html>")
    with patch("src.collectors.sub.lhm_http.urllib.request.urlopen", return_value=resp):
        assert _is_lhm_responding() is False


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timed out"),
        OSError("connection refused"),
        Exception("generic failure"),
    ],
)
def test_responding_connection_errors_are_false(exc):
    """urlopen raising (LHM down / timeout) → False, never propagates."""
    with patch("src.collectors.sub.lhm_http.urllib.request.urlopen", side_effect=exc):
        assert _is_lhm_responding() is False


def test_responding_reads_with_byte_cap():
    """read() is called with the defensive byte cap, not unbounded."""
    resp = _mock_response(json.dumps({"Children": []}).encode())
    with patch("src.collectors.sub.lhm_http.urllib.request.urlopen", return_value=resp):
        _is_lhm_responding()

    resp.read.assert_called_once_with(_MAX_RESPONSE_BYTES)
