"""Verifies OutputPanel ANSI/colorama → HTML translation and \\r last-line replace.

Coverage targets (from Eng Review): every Fore/Style code we use, the
\\r line-redraw semantics that AnimatedProgressBar relies on, and basic
append/clear behavior.
"""

from __future__ import annotations

import pytest
from colorama import Fore, Style

from src.gui.widgets.output_panel import OutputPanel, ansi_to_html


@pytest.mark.parametrize(
    "code, hex_color",
    [
        (Fore.CYAN, "#00E5CC"),
        (Fore.GREEN, "#4ADE80"),
        (Fore.YELLOW, "#FFB547"),
        (Fore.RED, "#FF6B6B"),
        (Fore.BLUE, "#60A5FA"),
        (Fore.MAGENTA, "#D183E8"),
        (Fore.WHITE, "#E8E6E3"),
    ],
)
def test_ansi_to_html_translates_each_color(code, hex_color):
    html = ansi_to_html(f"{code}hello{Style.RESET_ALL}")
    assert hex_color.lower() in html.lower()
    assert "hello" in html


def test_ansi_to_html_strips_codes_when_no_match():
    html = ansi_to_html("plain text")
    assert html == "plain text"


def test_ansi_to_html_escapes_html_entities():
    html = ansi_to_html(f"{Fore.CYAN}<b>x</b>{Style.RESET_ALL}")
    assert "&lt;b&gt;" in html
    assert "<b>x</b>" not in html


def test_ansi_to_html_handles_dim_style():
    html = ansi_to_html(f"{Style.DIM}quiet{Style.RESET_ALL}")
    assert "opacity" in html
    assert "quiet" in html


def test_output_panel_append_line(qtbot):
    panel = OutputPanel()
    qtbot.addWidget(panel)
    panel.append_line(f"{Fore.GREEN}OK done{Style.RESET_ALL}")
    assert "OK done" in panel._text.toPlainText()


def test_output_panel_carriage_return_replaces_last_line(qtbot):
    """Repeated \\r-redraws (the AnimatedProgressBar pattern) must not stack up."""
    panel = OutputPanel()
    qtbot.addWidget(panel)
    panel.append_line("\r[#####.....] 50%")
    panel.append_line("\r[##########] 100%")
    text = panel._text.toPlainText()
    assert "100%" in text
    assert "50%" not in text  # first frame retained, second frame visible


def test_output_panel_clear_log(qtbot):
    panel = OutputPanel()
    qtbot.addWidget(panel)
    panel.append_line("noise")
    panel.clear_log()
    assert panel._text.toPlainText() == ""


def test_output_panel_blank_line_is_inserted(qtbot):
    panel = OutputPanel()
    qtbot.addWidget(panel)
    panel.append_line("first line")
    panel.append_line("")
    panel.append_line("second line")
    text = panel._text.toPlainText()
    assert "first line" in text
    assert "second line" in text
    lines = text.splitlines()
    blank_lines = [l for l in lines if l.strip() == ""]
    assert len(blank_lines) >= 1, "expected at least one blank line between content lines"
