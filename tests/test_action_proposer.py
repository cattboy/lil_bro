"""
Tests for src/llm/action_proposer.py.
All LLM calls are mocked — no real model is loaded.
"""
import json
import pytest
from unittest.mock import MagicMock

from src.llm.action_proposer import (
    build_llm_input,
    propose_actions,
    _parse_proposals,
    _build_fallback,
    _is_fail,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

HARDWARE = {
    "cpu": "Intel Core i5-12400 (6 cores, 2500 MHz)",
    "gpu": "NVIDIA GeForce RTX 3060",
    "gpu_driver": "546.33",
    "ram_gb": 16.0,
    "ram_mhz": 2133,
    "os": "Windows 11 Pro",
    "motherboard": "ASUS TUF B660M-PLUS",
}

FAIL_DISPLAY = {
    "check": "display",
    "status": "WARNING",
    "current": 60,
    "expected": 144,
    "message": "Monitor running at 60Hz but supports up to 144Hz.",
    "can_auto_fix": True,
}

FAIL_XMP = {
    "check": "xmp",
    "status": "WARNING",
    "current": 2133,
    "message": "RAM running at 2133MHz — base JEDEC speed.",
    "can_auto_fix": False,
}

FAIL_POWER = {
    "check": "power_plan",
    "status": "WARNING",
    "current": "Balanced",
    "expected": "High Performance",
    "message": "Power plan is 'Balanced'.",
    "can_auto_fix": True,
}

OK_REBAR = {
    "check": "rebar",
    "status": "OK",
    "current": True,
    "message": "Resizable BAR is ENABLED.",
    "can_auto_fix": False,
}


# ── build_llm_input ───────────────────────────────────────────────────────────

def test_build_llm_input_only_includes_fail_findings():
    findings = [FAIL_DISPLAY, OK_REBAR, FAIL_XMP]
    result = build_llm_input(HARDWARE, findings)
    assert result["hardware"] == HARDWARE
    checks = [f["check"] for f in result["findings"]]
    assert "display" in checks
    assert "xmp" in checks
    assert "rebar" not in checks


def test_build_llm_input_display_fields():
    result = build_llm_input(HARDWARE, [FAIL_DISPLAY])
    entry = result["findings"][0]
    assert entry["check"] == "display"
    assert entry["current_hz"] == 60
    assert entry["max_available_hz"] == 144
    assert entry["status"] == "FAIL"


def test_build_llm_input_xmp_fields():
    result = build_llm_input(HARDWARE, [FAIL_XMP])
    entry = result["findings"][0]
    assert entry["check"] == "xmp"
    assert entry["current_mhz"] == 2133


def test_build_llm_input_power_plan_fields():
    result = build_llm_input(HARDWARE, [FAIL_POWER])
    entry = result["findings"][0]
    assert entry["check"] == "power_plan"
    assert entry["current_plan"] == "Balanced"


def test_build_llm_input_empty_when_all_ok():
    result = build_llm_input(HARDWARE, [OK_REBAR])
    assert result["findings"] == []


# ── _parse_proposals ──────────────────────────────────────────────────────────

def test_parse_proposals_valid_json():
    raw = '[{"finding": "display", "severity": "HIGH", "explanation": "test", "proposed_action": "fix it", "can_auto_fix": true}]'
    result = _parse_proposals(raw)
    assert result is not None
    assert len(result) == 1
    assert result[0]["finding"] == "display"


def test_parse_proposals_with_preamble():
    raw = 'Here are the recommendations:\n[{"finding": "xmp", "severity": "HIGH", "explanation": "test", "proposed_action": "fix", "can_auto_fix": false}]'
    result = _parse_proposals(raw)
    assert result is not None
    assert result[0]["finding"] == "xmp"


def test_parse_proposals_invalid_json_returns_none():
    assert _parse_proposals("not json at all") is None
    assert _parse_proposals("[]garbage after") is not None  # valid empty list


def test_parse_proposals_empty_array():
    result = _parse_proposals("[]")
    assert result == []


def test_parse_proposals_no_brackets_returns_none():
    assert _parse_proposals('{"finding": "display"}') is None


# ── _build_fallback ───────────────────────────────────────────────────────────

def test_fallback_only_for_fail_findings():
    findings = [FAIL_DISPLAY, OK_REBAR, FAIL_XMP]
    result = _build_fallback(findings)
    checks = [p["finding"] for p in result]
    assert "display" in checks
    assert "xmp" in checks
    assert "rebar" not in checks


def test_fallback_proposals_have_required_fields():
    result = _build_fallback([FAIL_DISPLAY])
    assert len(result) == 1
    p = result[0]
    assert "finding" in p
    assert "severity" in p
    assert "explanation" in p
    assert "proposed_action" in p
    assert "can_auto_fix" in p


def test_fallback_unknown_check_is_skipped():
    unknown = {"check": "unknown_check", "status": "WARNING"}
    result = _build_fallback([unknown])
    assert result == []


# ── propose_actions ───────────────────────────────────────────────────────────

def test_propose_actions_no_fail_findings_returns_empty():
    result = propose_actions(HARDWARE, [OK_REBAR], llm=None)
    assert result == []


def test_propose_actions_uses_fallback_when_llm_is_none():
    findings = [FAIL_DISPLAY, FAIL_POWER]
    result = propose_actions(HARDWARE, findings, llm=None)
    assert len(result) == 2
    # Both should be HIGH severity → fallback templates
    checks = [p["finding"] for p in result]
    assert "display" in checks
    assert "power_plan" in checks


def test_propose_actions_sorted_by_severity():
    # display=HIGH, power_plan=HIGH → both HIGH; add a LOW (temp_folders)
    fail_temp = {
        "check": "temp_folders",
        "status": "WARNING",
        "current": 2 * 1024 ** 3,
        "message": "temp bloat",
        "can_auto_fix": True,
    }
    fail_rebar = {
        "check": "rebar",
        "status": "WARNING",
        "current": False,
        "message": "rebar off",
        "can_auto_fix": False,
    }
    findings = [fail_temp, FAIL_XMP, fail_rebar]
    result = propose_actions(HARDWARE, findings, llm=None)
    severities = [p["severity"] for p in result]
    order_vals = [{"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(s, 2) for s in severities]
    assert order_vals == sorted(order_vals)


def _make_mock_llm(response_json: str):
    """Returns a mock Llama instance that returns the given string."""
    mock = MagicMock()
    mock.create_chat_completion.return_value = {
        "choices": [{"message": {"content": response_json}}]
    }
    return mock


def test_propose_actions_uses_llm_output_when_valid():
    llm_output = json.dumps([
        {
            "finding": "display",
            "severity": "HIGH",
            "explanation": "LLM explanation here.",
            "proposed_action": "Set to 144Hz",
            "can_auto_fix": True,
        }
    ])
    mock_llm = _make_mock_llm(llm_output)
    result = propose_actions(HARDWARE, [FAIL_DISPLAY], llm=mock_llm)
    assert len(result) == 1
    assert result[0]["explanation"] == "LLM explanation here."


def test_propose_actions_falls_back_on_bad_llm_json():
    mock_llm = _make_mock_llm("this is not json")
    result = propose_actions(HARDWARE, [FAIL_DISPLAY], llm=mock_llm)
    # Should fall back to static template
    assert len(result) == 1
    assert result[0]["finding"] == "display"
    # Fallback explanation is the static one, not "LLM explanation"
    assert "LLM explanation" not in result[0]["explanation"]


def test_propose_actions_llm_called_once_on_bad_first_response_then_falls_back():
    mock_llm = _make_mock_llm("garbage")
    propose_actions(HARDWARE, [FAIL_DISPLAY], llm=mock_llm)
    # Should have retried twice before falling back
    assert mock_llm.create_chat_completion.call_count == 2


# ── _is_fail ─────────────────────────────────────────────────────────────────

def test_is_fail_recognises_warning_and_error():
    assert _is_fail({"status": "WARNING"}) is True
    assert _is_fail({"status": "ERROR"}) is True
    assert _is_fail({"status": "OK"}) is False
    assert _is_fail({"status": "UNKNOWN"}) is False
