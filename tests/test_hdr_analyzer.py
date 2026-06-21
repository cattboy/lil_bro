"""Tests for the pure HDR analyzer (src/agent_tools/hdr.py)."""

from src.agent_tools.hdr import (
    HDR_PRIORITY,
    analyze_hdr,
    hdr_priority_hint_lines,
    parse_nvidia_gpu,
)


# ── parse_nvidia_gpu ──────────────────────────────────────────────────────────


def test_parse_rtx_high_tier():
    g = parse_nvidia_gpu("NVIDIA GeForce RTX 4070")
    assert g["is_rtx"] is True
    assert g["model"] == 4070
    assert g["series"] == 40
    assert g["low_tier"] is False


def test_parse_rtx_low_tier_fps_note():
    assert parse_nvidia_gpu("NVIDIA GeForce RTX 3050")["low_tier"] is True
    assert parse_nvidia_gpu("NVIDIA GeForce RTX 2060")["low_tier"] is True
    assert parse_nvidia_gpu("NVIDIA GeForce RTX 4060 Ti")["low_tier"] is True


def test_parse_rtx_5070_is_series_50():
    g = parse_nvidia_gpu("NVIDIA GeForce RTX 5070")
    assert g["is_rtx"] is True
    assert g["series"] == 50


def test_parse_non_rtx():
    assert parse_nvidia_gpu("NVIDIA GeForce GTX 1080")["is_rtx"] is False
    assert parse_nvidia_gpu("AMD Radeon RX 7900 XTX")["is_rtx"] is False
    assert parse_nvidia_gpu(None)["is_rtx"] is False
    assert parse_nvidia_gpu("")["is_rtx"] is False


# ── helpers for analyze_hdr ──────────────────────────────────────────────────


def _hdr_status(*, capable=True, enabled=True, is_win11=True, auto=False, primary=True):
    return {
        "determined": True,
        "is_win11": is_win11,
        "auto_hdr_enabled": auto,
        "displays": [
            {"device": "\\\\.\\DISPLAY1", "is_primary": primary,
             "hdr_capable": capable, "hdr_enabled": enabled, "source": "displayconfig"},
        ],
    }


def _rtx(gpu="NVIDIA GeForce RTX 4070", rtx_hdr_on=False):
    return {"NVIDIA": [{"GPU": gpu}], "NVIDIAProfile": {"rtx_hdr_enabled": rtx_hdr_on}}


# ── analyze_hdr: undetermined → hidden ───────────────────────────────────────


def test_undetermined_hides_card():
    assert analyze_hdr({})["determined"] is False
    assert analyze_hdr({})["state"] == "hidden"
    assert analyze_hdr({"HDRStatus": {"determined": False, "error": "DisplayConfig zero"}})["state"] == "hidden"


def test_not_hdr_capable():
    r = analyze_hdr({"HDRStatus": _hdr_status(capable=False)})
    assert r["determined"] is True
    assert r["state"] == "not_applicable"
    assert r["status"] == "NA"


def test_hdr_off_recommends_base():
    r = analyze_hdr({"HDRStatus": _hdr_status(enabled=False)})
    assert r["state"] == "hdr_off"
    assert r["recommended_tier"] == "base_hdr"
    assert r["deep_link"] == "ms-settings:display"


# ── analyze_hdr: RTX path (highest priority) ─────────────────────────────────


def test_rtx_on_is_optimal():
    specs = {"HDRStatus": _hdr_status(), **_rtx(rtx_hdr_on=True)}
    r = analyze_hdr(specs)
    assert r["state"] == "optimal"
    assert r["recommended_tier"] == "rtx_hdr"


def test_rtx_off_recommends_rtx_with_nvidia_link():
    specs = {"HDRStatus": _hdr_status(auto=True), **_rtx(rtx_hdr_on=False)}
    r = analyze_hdr(specs)
    # RTX outranks Auto HDR even when Auto HDR is already on.
    assert r["state"] == "suboptimal"
    assert r["recommended_tier"] == "rtx_hdr"
    assert r["deep_link"] == "nvidia_app"
    assert r["fps_note"] is False  # 4070 is not low tier


def test_rtx_low_tier_sets_fps_note():
    specs = {"HDRStatus": _hdr_status(), **_rtx(gpu="NVIDIA GeForce RTX 3050", rtx_hdr_on=False)}
    assert analyze_hdr(specs)["fps_note"] is True


# ── analyze_hdr: Auto HDR path (Win11, no RTX) ───────────────────────────────


def test_auto_hdr_off_recommends_auto():
    r = analyze_hdr({"HDRStatus": _hdr_status(auto=False)})
    assert r["state"] == "suboptimal"
    assert r["recommended_tier"] == "auto_hdr"
    assert r["deep_link"] == "ms-settings:display"


def test_auto_hdr_on_is_optimal():
    r = analyze_hdr({"HDRStatus": _hdr_status(auto=True)})
    assert r["state"] == "optimal"
    assert r["recommended_tier"] == "auto_hdr"


# ── analyze_hdr: Win10 base path ─────────────────────────────────────────────


def test_win10_hdr_on_is_optimal_base():
    r = analyze_hdr({"HDRStatus": _hdr_status(is_win11=False, auto=False)})
    assert r["state"] == "optimal"
    assert r["recommended_tier"] == "base_hdr"


# ── analyze_hdr: multi-monitor (outside-voice #6) ────────────────────────────


def test_non_primary_hdr_panel_surfaced():
    status = {
        "determined": True, "is_win11": True, "auto_hdr_enabled": False,
        "displays": [
            {"device": "PRIMARY", "is_primary": True, "hdr_capable": False, "hdr_enabled": False},
            {"device": "HDR_SECONDARY", "is_primary": False, "hdr_capable": True, "hdr_enabled": True},
        ],
    }
    r = analyze_hdr({"HDRStatus": status})
    assert r["on_non_primary"] is True
    assert r["primary_device"] == "HDR_SECONDARY"
    assert r["state"] == "suboptimal"  # HDR on, Auto HDR off


# ── hint lines derive from the shared priority constant ──────────────────────


def test_hint_lines_match_priority_order():
    lines = hdr_priority_hint_lines()
    assert len(lines) == len(HDR_PRIORITY) == 3
    assert lines[0].startswith("1.")
    assert "RTX HDR" in lines[0]
