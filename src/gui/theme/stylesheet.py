"""QSS builder. Assembles the application stylesheet from per-component sections.

``build_stylesheet()`` is the sole public entry point. Each ``_qss_*`` helper
lives in a domain-scoped sibling module; colors are passed as ``c`` (the
``COLORS`` dict), fonts are read from the module-level ``FONTS`` import inside
each helper module.
"""

from __future__ import annotations

from src.gui.theme.tokens import COLORS
from src.gui.theme.stylesheet_foundation import _qss_base, _qss_chrome, _qss_text
from src.gui.theme.stylesheet_interactive import (
    _qss_buttons,
    _qss_log_toolbar,
    _qss_sidebar,
    _qss_status_bar,
)
from src.gui.theme.stylesheet_monitoring import (
    _qss_chart,
    _qss_phase_row,
    _qss_poll,
    _qss_stat_cards,
)
from src.gui.theme.stylesheet_dialogs import (
    _qss_batch_dialog,
    _qss_confirm_dialog,
    _qss_mouse_ready_dialog,
    _qss_output_header,
    _qss_splash,
)


def build_stylesheet() -> str:
    """Return the QSS for the entire app, with DESIGN.md tokens substituted."""
    c = COLORS
    return "\n".join([
        # phaseCard base rules (must precede _qss_phase_row cascade override)
        _qss_base(c),
        _qss_buttons(c),
        _qss_text(c),
        _qss_chrome(c),
        _qss_sidebar(c),
        _qss_stat_cards(c),
        _qss_chart(c),
        _qss_poll(c),
        _qss_phase_row(c),
        _qss_output_header(c),
        _qss_log_toolbar(c),
        _qss_status_bar(c),
        _qss_batch_dialog(c),
        _qss_confirm_dialog(c),
        _qss_mouse_ready_dialog(c),
        _qss_splash(c),
    ])
