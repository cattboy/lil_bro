"""
Tests for src/utils/_console.py (resize_console_window).

The function does isolated ctypes/Windows-console IO and swallows all
exceptions. We never touch the real Win32 API — ctypes.windll is patched so
we can observe which calls are made (or skipped) under different conditions.
The function-local `import ctypes` / `import os` means we patch the real
`ctypes`/`os` modules, which the function re-imports at call time.
"""
import sys
import types
from unittest.mock import MagicMock

import pytest

from src.utils._console import resize_console_window


def _install_fake_ctypes(monkeypatch, user32=None, kernel32=None, hwnd=12345):
    """Replace ctypes.windll with mocks; returns (kernel32, user32)."""
    import ctypes

    kernel32 = kernel32 or MagicMock()
    user32 = user32 or MagicMock()
    kernel32.GetConsoleWindow.return_value = hwnd

    fake_windll = types.SimpleNamespace(kernel32=kernel32, user32=user32)
    monkeypatch.setattr(ctypes, "windll", fake_windll, raising=False)
    return kernel32, user32


def test_returns_none_and_does_not_raise(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    _install_fake_ctypes(monkeypatch)
    assert resize_console_window() is None


def test_skips_when_windows_terminal(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "some-guid")
    kernel32, user32 = _install_fake_ctypes(monkeypatch)
    resize_console_window()
    # Early-return before touching the console window at all.
    kernel32.GetConsoleWindow.assert_not_called()
    user32.SetWindowPos.assert_not_called()


def test_skips_when_no_console_window(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    # GetConsoleWindow returns 0 (no console) → bail before any sizing.
    kernel32, user32 = _install_fake_ctypes(monkeypatch, hwnd=0)
    resize_console_window()
    kernel32.GetConsoleWindow.assert_called_once()
    user32.GetSystemMetrics.assert_not_called()
    user32.SetWindowPos.assert_not_called()


def test_resizes_centered_on_normal_console(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    user32 = MagicMock()
    # 1920x1080 screen; window is not maximized.
    user32.GetSystemMetrics.side_effect = lambda idx: (1920, 1080)[idx]
    user32.IsZoomed.return_value = False
    kernel32, user32 = _install_fake_ctypes(monkeypatch, user32=user32, hwnd=999)

    resize_console_window()

    # 80% of 1920x1080 = 1536x864, centered at (192, 108).
    args = user32.SetWindowPos.call_args.args
    # SetWindowPos(hwnd, insertAfter, x, y, w, h, flags)
    assert args[0] == 999
    assert args[2] == 192   # x
    assert args[3] == 108   # y
    assert args[4] == 1536  # w
    assert args[5] == 864   # h
    user32.ShowWindow.assert_not_called()  # not zoomed → no SW_RESTORE
    user32.SetForegroundWindow.assert_called_once_with(999)


def test_restores_when_maximized(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    user32 = MagicMock()
    user32.GetSystemMetrics.side_effect = lambda idx: (1920, 1080)[idx]
    user32.IsZoomed.return_value = True
    _install_fake_ctypes(monkeypatch, user32=user32, hwnd=999)

    resize_console_window()

    # SW_RESTORE (9) issued because the window was maximized.
    user32.ShowWindow.assert_called_once_with(999, 9)


def test_swallows_exceptions(monkeypatch):
    monkeypatch.delenv("WT_SESSION", raising=False)
    import ctypes

    class Boom:
        @property
        def kernel32(self):
            raise OSError("ctypes exploded")

    monkeypatch.setattr(ctypes, "windll", Boom(), raising=False)
    # Must not propagate — function is best-effort and wraps everything in try.
    assert resize_console_window() is None
