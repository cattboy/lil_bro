"""Tests for the pure Auto HDR registry-string parser (hdr_dumper.parse_auto_hdr).

The DisplayConfig ctypes path and the winreg I/O need real Windows and are
exercised by scripts/probe_hdr.py on hardware; the token surgery is pure and
unit-tested exhaustively here (the write counterpart is TODO T-039).
"""

from src.collectors.sub.hdr_dumper import parse_auto_hdr


def test_token_enabled():
    assert parse_auto_hdr("VRROptimizeEnable=1;AutoHDREnable=1;SwapEffectUpgradeEnable=1;") is True


def test_token_disabled():
    assert parse_auto_hdr("AutoHDREnable=0;VRROptimizeEnable=1;") is False


def test_token_absent_returns_none():
    # Fresh install: the global default has never been set.
    assert parse_auto_hdr("VRROptimizeEnable=1;SwapEffectUpgradeEnable=1;") is None


def test_none_and_empty():
    assert parse_auto_hdr(None) is None
    assert parse_auto_hdr("") is None


def test_tolerates_whitespace_and_order():
    assert parse_auto_hdr("  AutoHDREnable = 1 ; VRROptimizeEnable=0 ") is True
    assert parse_auto_hdr("DXGIEffects=1028;AutoHDREnable=0") is False


def test_ignores_malformed_segments():
    assert parse_auto_hdr("garbage;;AutoHDREnable=1;=;") is True
