"""
tests/test_formatting.py — Design system compliance + formatting function tests.

Covers:
  - _ASCII_FALLBACK detection (3 tests)
  - Unicode fallbacks for icon-bearing functions (8 tests)
  - print_key_value (3 tests)
  - print_section_divider (4 tests)
  - print_prompt regression (2 tests)
  - print_proposal regression (5 tests)
  - resize_console_window (3 + 5 regression tests)
  - DESIGN.md sync (2 tests)
"""

import importlib
import io
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from colorama import Fore, Style

import src.utils.formatting as formatting


# ── _ASCII_FALLBACK detection (3 tests) ───────────────────────────────────────
# These test the init-time flag by reloading the module with patched encoding.
# They don't use capsys (reload disrupts it) — they only check the flag value.

class _FakeStdout:
    """Minimal stdout stand-in with a settable encoding attribute."""
    def __init__(self, encoding):
        self.encoding = encoding
    def write(self, s): pass
    def flush(self): pass


def test_unicode_safe_utf8():
    """UTF-8 terminal → _ASCII_FALLBACK is False (Unicode icons used)."""
    saved = sys.stdout
    try:
        sys.stdout = _FakeStdout('utf-8')
        importlib.reload(formatting)
        assert formatting._ASCII_FALLBACK is False
    finally:
        sys.stdout = saved
        importlib.reload(formatting)


def test_unicode_safe_cp437():
    """CP437 terminal (Windows CMD) → _ASCII_FALLBACK is True (ASCII fallbacks)."""
    saved = sys.stdout
    try:
        sys.stdout = _FakeStdout('cp437')
        importlib.reload(formatting)
        assert formatting._ASCII_FALLBACK is True
    finally:
        sys.stdout = saved
        importlib.reload(formatting)


def test_unicode_safe_no_encoding_attr():
    """stdout with no encoding attribute → getattr fallback to utf-8 → False."""
    fake = io.StringIO()
    if hasattr(fake, 'encoding'):
        delattr(type(fake), 'encoding') if 'encoding' in type(fake).__dict__ else None
    # StringIO always has encoding, use a custom object
    class BareStdout:
        def write(self, s): pass
        def flush(self): pass
    bare = BareStdout()
    assert not hasattr(bare, 'encoding')
    saved = sys.stdout
    try:
        sys.stdout = bare
        importlib.reload(formatting)
        assert formatting._ASCII_FALLBACK is False
    finally:
        sys.stdout = saved
        importlib.reload(formatting)


# ── Unicode fallbacks (8 tests) ─────────────────────────────────────────────
# Monkeypatch _ASCII_FALLBACK directly to avoid module reload issues with capsys.

def test_print_success_unicode(capsys, monkeypatch):
    """Unicode mode: print_success uses ✓."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', False)
    formatting.print_success("done")
    out = capsys.readouterr().out
    assert "\u2713" in out


def test_print_success_ascii(capsys, monkeypatch):
    """ASCII mode: print_success uses OK."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', True)
    formatting.print_success("done")
    out = capsys.readouterr().out
    assert "OK " in out


def test_print_warning_unicode(capsys, monkeypatch):
    """Unicode mode: print_warning uses ⚠."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', False)
    formatting.print_warning("caution")
    out = capsys.readouterr().out
    assert "\u26a0" in out


def test_print_warning_ascii(capsys, monkeypatch):
    """ASCII mode: print_warning uses WARN."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', True)
    formatting.print_warning("caution")
    out = capsys.readouterr().out
    assert "WARN " in out


def test_print_error_unicode(capsys, monkeypatch):
    """Unicode mode: print_error uses ✗."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', False)
    formatting.print_error("broke")
    out = capsys.readouterr().out
    assert "\u2717" in out


def test_print_error_ascii(capsys, monkeypatch):
    """ASCII mode: print_error uses FAIL."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', True)
    formatting.print_error("broke")
    out = capsys.readouterr().out
    assert "FAIL " in out


def test_print_info_unicode(capsys, monkeypatch):
    """Unicode mode: print_info uses ℹ."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', False)
    formatting.print_info("note")
    out = capsys.readouterr().out
    assert "\u2139" in out


def test_print_info_ascii(capsys, monkeypatch):
    """ASCII mode: print_info uses INFO."""
    monkeypatch.setattr(formatting, '_ASCII_FALLBACK', True)
    formatting.print_info("note")
    out = capsys.readouterr().out
    assert "INFO " in out


# ── print_key_value (3 tests) ───────────────────────────────────────────────

def test_key_value_default_color(capsys):
    """print_key_value uses cyan by default for the value."""
    formatting.print_key_value("CPU", "Ryzen 9")
    out = capsys.readouterr().out
    assert "CPU:" in out
    assert "Ryzen 9" in out


def test_key_value_custom_color(capsys):
    """print_key_value accepts a custom value_color."""
    formatting.print_key_value("AI Model", "ready", value_color=Fore.GREEN)
    out = capsys.readouterr().out
    assert "AI Model:" in out
    assert "ready" in out
    assert Fore.GREEN in out


def test_key_value_dim_label(capsys):
    """print_key_value renders the label with Style.DIM."""
    formatting.print_key_value("GPU", "RTX 4090")
    out = capsys.readouterr().out
    assert Style.DIM in out


# ── print_section_divider (4 tests) ─────────────────────────────────────────

def test_section_divider_no_label(capsys):
    """print_section_divider with no label produces a line of dashes."""
    formatting.print_section_divider()
    out = capsys.readouterr().out.strip()
    # Strip ANSI codes for length check
    clean = out.replace(Style.DIM, "").replace(Style.RESET_ALL, "")
    assert len(clean) >= 20


def test_section_divider_with_label(capsys):
    """print_section_divider with a label embeds it in the line."""
    formatting.print_section_divider("Phase 3")
    out = capsys.readouterr().out
    assert "Phase 3" in out


def test_section_divider_zero_width_floor(capsys):
    """Even with a tiny terminal, the divider is at least 20 chars wide."""
    with patch('src.utils.formatting.shutil.get_terminal_size', return_value=os.terminal_size((5, 24))):
        formatting.print_section_divider()
    out = capsys.readouterr().out.strip()
    clean = out.replace(Style.DIM, "").replace(Style.RESET_ALL, "")
    assert len(clean) >= 20


def test_section_divider_narrow_terminal(capsys):
    """Narrow terminal gets max(20, cols) width."""
    with patch('src.utils.formatting.shutil.get_terminal_size', return_value=os.terminal_size((15, 24))):
        formatting.print_section_divider("Test")
    out = capsys.readouterr().out
    assert "Test" in out


# ── print_prompt regression (2 tests) ───────────────────────────────────────

def test_print_prompt_has_angle_prefix(capsys):
    """Regression: print_prompt must output '> ' prefix."""
    formatting.print_prompt("Choose: ")
    out = capsys.readouterr().out
    assert "> " in out
    assert "Choose: " in out


def test_print_prompt_no_newline(capsys):
    """print_prompt should NOT end with a newline."""
    formatting.print_prompt("test")
    out = capsys.readouterr().out
    assert not out.endswith("\n")


# ── print_proposal regression (5 tests) ─────────────────────────────────────

def test_print_proposal_explanation_white(capsys):
    """Regression: explanation text must use Fore.WHITE, not Style.DIM."""
    formatting.print_proposal(1, "HIGH", "Test", "Explanation here", "Do the thing", True)
    out = capsys.readouterr().out
    lines = out.strip().split("\n")
    explanation_line = lines[1]  # second line is explanation
    assert Fore.WHITE in explanation_line
    assert "Explanation here" in explanation_line


def test_print_proposal_fix_dim(capsys):
    """Regression: fix line must use Style.DIM."""
    formatting.print_proposal(1, "HIGH", "Test", "Explain", "Fix action", True)
    out = capsys.readouterr().out
    lines = out.strip().split("\n")
    fix_line = lines[2]  # third line is fix
    assert Style.DIM in fix_line
    assert "Fix:" in fix_line


def test_print_proposal_severity_colors(capsys):
    """Each severity level gets the correct color in the header."""
    for severity, expected_color in [("HIGH", Fore.RED), ("MEDIUM", Fore.YELLOW), ("LOW", Fore.CYAN)]:
        formatting.print_proposal(1, severity, "Title", "Explain", "Action", True)
        out = capsys.readouterr().out
        header_line = out.strip().split("\n")[0]
        assert expected_color in header_line, f"{severity} should use {expected_color!r}"


def test_print_proposal_auto_tag(capsys):
    """can_auto_fix=True shows [AUTO] in green."""
    formatting.print_proposal(1, "LOW", "T", "E", "A", can_auto_fix=True)
    out = capsys.readouterr().out
    assert "[AUTO]" in out
    assert Fore.GREEN in out


def test_print_proposal_manual_tag(capsys):
    """can_auto_fix=False shows [MANUAL] in dim."""
    formatting.print_proposal(1, "LOW", "T", "E", "A", can_auto_fix=False)
    out = capsys.readouterr().out
    assert "[MANUAL]" in out


# ── resize_console_window (3 + 5 regression tests) ──────────────────────────

def _make_resize_mocks():
    """Factory for resize_console_window mock objects."""
    from unittest.mock import MagicMock
    mock_kernel32 = MagicMock()
    mock_user32   = MagicMock()
    mock_kernel32.GetConsoleWindow.return_value = 0xABCD
    mock_user32.GetSystemMetrics.side_effect = lambda idx: 1920 if idx == 0 else 1080
    mock_user32.IsZoomed.return_value = False
    return mock_kernel32, mock_user32


@patch.dict(os.environ, {}, clear=False)
def test_resize_console_calls_setwindowpos():
    """Happy path: SetWindowPos is called with 80% of screen dims, centered."""
    from unittest.mock import MagicMock, patch
    os.environ.pop("WT_SESSION", None)
    mock_kernel32, mock_user32 = _make_resize_mocks()

    with patch('ctypes.windll') as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        mock_windll.user32   = mock_user32
        formatting.resize_console_window()

    expected_w = int(1920 * 0.8)  # 1536
    expected_h = int(1080 * 0.8)  # 864
    expected_x = (1920 - expected_w) // 2  # 192
    expected_y = (1080 - expected_h) // 2  # 108
    mock_user32.SetWindowPos.assert_called_once()
    call_args = mock_user32.SetWindowPos.call_args[0]
    assert call_args[1:5] == (None, expected_x, expected_y, expected_w)
    assert call_args[5] == expected_h


def test_resize_console_no_hwnd_is_noop():
    """GetConsoleWindow returns 0 → SetWindowPos is never called."""
    from unittest.mock import MagicMock, patch
    mock_kernel32 = MagicMock()
    mock_user32   = MagicMock()
    mock_kernel32.GetConsoleWindow.return_value = 0

    with patch('ctypes.windll') as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        mock_windll.user32   = mock_user32
        formatting.resize_console_window()

    mock_user32.SetWindowPos.assert_not_called()


def test_resize_console_exception_is_silent():
    """Any exception inside resize_console_window is swallowed silently."""
    from unittest.mock import patch
    with patch('ctypes.windll', side_effect=Exception("ctypes exploded")):
        formatting.resize_console_window()   # must not raise


# Regression: ISSUE-003 — resize_console_window steals keyboard focus
# Found by /qa on 2026-03-25

@patch.dict(os.environ, {"WT_SESSION": "fake-guid"})
def test_resize_skips_inside_windows_terminal():
    """WT_SESSION env var set → resize is skipped entirely (no Win32 calls)."""
    from unittest.mock import patch
    with patch('ctypes.windll') as mock_windll:
        formatting.resize_console_window()
    mock_windll.kernel32.GetConsoleWindow.assert_not_called()


@patch.dict(os.environ, {}, clear=False)
def test_resize_no_showwindow_when_not_maximized():
    """Window is NOT maximized → ShowWindow(SW_RESTORE) is NOT called."""
    from unittest.mock import patch
    os.environ.pop("WT_SESSION", None)
    mock_kernel32, mock_user32 = _make_resize_mocks()
    mock_user32.IsZoomed.return_value = False

    with patch('ctypes.windll') as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        mock_windll.user32   = mock_user32
        formatting.resize_console_window()

    mock_user32.ShowWindow.assert_not_called()


@patch.dict(os.environ, {}, clear=False)
def test_resize_restores_when_maximized():
    """Window IS maximized → ShowWindow(SW_RESTORE=9) is called."""
    from unittest.mock import patch
    os.environ.pop("WT_SESSION", None)
    mock_kernel32, mock_user32 = _make_resize_mocks()
    mock_user32.IsZoomed.return_value = True

    with patch('ctypes.windll') as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        mock_windll.user32   = mock_user32
        formatting.resize_console_window()

    mock_user32.ShowWindow.assert_called_once_with(0xABCD, 9)


@patch.dict(os.environ, {}, clear=False)
def test_resize_uses_noactivate_flag():
    """SetWindowPos must use SWP_NOACTIVATE (0x0010), not SWP_SHOWWINDOW (0x0040)."""
    from unittest.mock import patch
    os.environ.pop("WT_SESSION", None)
    mock_kernel32, mock_user32 = _make_resize_mocks()

    with patch('ctypes.windll') as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        mock_windll.user32   = mock_user32
        formatting.resize_console_window()

    flags = mock_user32.SetWindowPos.call_args[0][6]
    SWP_NOACTIVATE = 0x0010
    SWP_SHOWWINDOW = 0x0040
    assert flags & SWP_NOACTIVATE, "SWP_NOACTIVATE must be set"
    assert not (flags & SWP_SHOWWINDOW), "SWP_SHOWWINDOW must NOT be set"


@patch.dict(os.environ, {}, clear=False)
def test_resize_calls_setforegroundwindow():
    """SetForegroundWindow must be called after resize to restore keyboard focus."""
    from unittest.mock import patch
    os.environ.pop("WT_SESSION", None)
    mock_kernel32, mock_user32 = _make_resize_mocks()

    with patch('ctypes.windll') as mock_windll:
        mock_windll.kernel32 = mock_kernel32
        mock_windll.user32   = mock_user32
        formatting.resize_console_window()

    mock_user32.SetForegroundWindow.assert_called_once_with(0xABCD)


# ── DESIGN.md sync (2 tests) ────────────────────────────────────────────────

_DESIGN_MD = Path(__file__).resolve().parent.parent / "DESIGN.md"

_REQUIRED_TOKENS = [
    "Fore.CYAN",
    "Fore.GREEN",
    "Fore.YELLOW",
    "Fore.RED",
    "Fore.BLUE",
    "Fore.MAGENTA",
    "Fore.WHITE",
    "Style.DIM",
]


def test_design_md_has_fore_blue():
    """Fore.BLUE must be mapped in DESIGN.md colorama mapping section."""
    content = _DESIGN_MD.read_text(encoding="utf-8")
    assert "Fore.BLUE" in content, "DESIGN.md is missing Fore.BLUE in colorama mapping"


def test_design_md_all_tokens_mapped():
    """Every colorama token used in formatting.py must appear in DESIGN.md."""
    content = _DESIGN_MD.read_text(encoding="utf-8")
    missing = [t for t in _REQUIRED_TOKENS if t not in content]
    assert not missing, f"DESIGN.md missing colorama mappings: {missing}"
