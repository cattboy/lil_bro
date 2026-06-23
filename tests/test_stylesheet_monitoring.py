"""Exercises every QSS builder in ``stylesheet_monitoring`` against the real palette.

The real value of these tests: each builder is an f-string that interpolates
``c["..."]`` palette keys and ``FONTS[...]`` tokens. A missing key would raise
``KeyError`` at call time, and a malformed interpolation would leave a raw
``{c[...]}`` placeholder in the emitted QSS. Calling with the genuine
``theme.COLORS`` dict (not a hand-rolled fake) proves both can't happen.
"""

from __future__ import annotations

import pytest

from src.gui.theme.tokens import COLORS
from src.gui.theme.stylesheet_monitoring import (
    _qss_chart,
    _qss_dashboard_scroll,
    _qss_info_marker,
    _qss_phase_row,
    _qss_poll,
    _qss_stat_cards,
)


# (builder, a selector token the builder is contractually required to emit)
BUILDERS = [
    (_qss_stat_cards, "QFrame#dashboardCard"),
    (_qss_info_marker, "QLabel#infoMarker"),
    (_qss_chart, "QFrame#chartWrap"),
    (_qss_poll, "QFrame#pollWidget"),
    (_qss_dashboard_scroll, "QScrollArea#dashboardScroll"),
    (_qss_phase_row, "QFrame#phaseRow"),
]


@pytest.mark.parametrize("builder, selector", BUILDERS, ids=lambda v: getattr(v, "__name__", v))
def test_builder_returns_nonempty_str(builder, selector):
    qss = builder(COLORS)
    assert isinstance(qss, str)
    assert qss.strip(), f"{builder.__name__} returned empty QSS"


@pytest.mark.parametrize("builder, selector", BUILDERS, ids=lambda v: getattr(v, "__name__", v))
def test_builder_emits_expected_selector(builder, selector):
    qss = builder(COLORS)
    assert selector in qss, f"{builder.__name__} missing selector {selector!r}"


@pytest.mark.parametrize("builder, selector", BUILDERS, ids=lambda v: getattr(v, "__name__", v))
def test_builder_no_unresolved_interpolation(builder, selector):
    # If an f-string placeholder survived to the output, an unresolved
    # ``{c[`` / ``{FONTS[`` fragment would remain. The real palette resolves
    # every one of them.
    qss = builder(COLORS)
    assert "{c[" not in qss, f"{builder.__name__} left an unresolved palette placeholder"
    assert "{FONTS[" not in qss, f"{builder.__name__} left an unresolved FONTS placeholder"


def test_builders_do_not_raise_keyerror_with_real_palette():
    # The headline guarantee: none of the palette keys these f-strings read
    # are absent from the genuine COLORS dict.
    for builder, _selector in BUILDERS:
        try:
            builder(COLORS)
        except KeyError as exc:  # pragma: no cover - this is the failure we guard
            pytest.fail(f"{builder.__name__} raised KeyError({exc}) on the real palette")


def test_poll_emits_sev_tone_variants():
    # Poll widgets carry the sev=low|medium|high color cascade (DESIGN.md).
    qss = _qss_poll(COLORS)
    for sev in ("low", "medium", "high"):
        assert f'sev="{sev}"' in qss
