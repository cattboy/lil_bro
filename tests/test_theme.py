"""Verifies theme.py emits the DESIGN.md tokens the QSS depends on.

These tests guard against accidental token drift — if someone "tidies up"
theme.py and removes the cyan accent or drops scanline-affecting hooks,
QA catches it before users do. Token list mirrors DESIGN.md's color
palette exactly.
"""

from __future__ import annotations

import pytest

from src.gui import theme


REQUIRED_HEX = [
    "#1A1B23",  # deep
    "#24252F",  # surface
    "#2E2F3A",  # elevated
    "#363745",  # hover / border default
    "#00E5CC",  # accent
    "#4ADE80",  # success
    "#FFB547",  # warning
    "#FF6B6B",  # error
    "#E8E6E3",  # text primary
    "#9B9AA0",  # text secondary
    "#6B6A70",  # text muted
]


@pytest.mark.parametrize("hex_code", REQUIRED_HEX)
def test_qss_contains_design_md_token(hex_code):
    qss = theme.build_stylesheet()
    assert hex_code in qss, f"DESIGN.md token {hex_code} missing from QSS"


def test_qss_references_design_md_fonts():
    qss = theme.build_stylesheet()
    assert "JetBrains Mono" in qss
    assert "DM Sans" in qss


def test_colors_dict_keys_complete():
    expected = {
        "deep", "surface", "elevated", "hover",
        "accent", "accent_dim", "accent_glow",
        "success", "warning", "error", "info",
        "text_primary", "text_secondary", "text_muted",
        "border_default", "border_accent",
    }
    assert expected.issubset(theme.COLORS.keys())


def test_qss_phase_card_status_states_present():
    qss = theme.build_stylesheet()
    for status in ("active", "done", "failed"):
        assert f'phaseStatus="{status}"' in qss


def test_qss_primary_button_uses_accent():
    qss = theme.build_stylesheet()
    assert "#primary" in qss
    primary_block = qss.split("#primary")[1]
    assert "#00E5CC" in primary_block.split("}")[0]


def test_load_fonts_no_op_when_resources_missing(tmp_path, monkeypatch):
    # ``load_fonts`` lives in ``theme.helpers`` and binds ``_resources_dir``
    # from that module's namespace — patch it there, not on the package.
    monkeypatch.setattr("src.gui.theme.helpers._resources_dir", lambda: tmp_path)
    theme.load_fonts()  # must not raise  # must not raise
