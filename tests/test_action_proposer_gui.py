"""Tests for the GUI-facing `propose_for_check()` helper + public rename.

These tests pin down the contract that Dashboard widgets rely on:
- `FALLBACK_PROPOSALS` is importable under its public name (no underscore).
- `propose_for_check(check, finding)` returns one proposal dict matching the
  fallback template for the named check, on the LLM-None path.
- Unknown checks return None (no template, no proposal).
- A None `finding` arg returns the template directly (for static-text widgets).
"""
from __future__ import annotations

from src.llm.action_proposer import FALLBACK_PROPOSALS, propose_for_check


def test_propose_for_check_returns_fallback_when_no_llm():
    p = propose_for_check("mouse_polling", {"current_hz": 125, "threshold_hz": 500})
    assert p is not None
    assert "1000" in p["proposed_action"]
    assert p["can_auto_fix"] is False


def test_propose_for_check_display_proposal():
    p = propose_for_check("display", {"current": 60, "expected": 144})
    assert p is not None
    assert p["can_auto_fix"] is True
    assert "refresh rate" in p["explanation"].lower()


def test_propose_for_check_unknown_returns_none():
    assert propose_for_check("nonexistent_check", {}) is None


def test_propose_for_check_no_finding_returns_template():
    p = propose_for_check("mouse_polling")
    assert p is not None
    assert p["finding"] == "mouse_polling"
    assert p["severity"] == "MEDIUM"


def test_fallback_proposals_public_name():
    assert "mouse_polling" in FALLBACK_PROPOSALS
    assert "display" in FALLBACK_PROPOSALS
    assert "nvidia_profile" in FALLBACK_PROPOSALS
