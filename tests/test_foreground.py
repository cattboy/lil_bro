"""Tests for ``src.gui._foreground.bring_to_foreground`` (Win32 foreground bypass).

Mirrors the ctypes-patch idiom in ``tests/test_formatting.py``: patch
``ctypes.windll``, hand it MagicMock ``user32`` / ``kernel32``, then assert on the
Win32 calls. No real window / QApplication is needed — a MagicMock stands in for
the QWidget (``winId()`` returns a fake HWND int).
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from src.gui._foreground import bring_to_foreground


def _make_mocks(hwnd=0xABCD, fg_hwnd=0xABCD):
    """Build (window, kernel32, user32) mocks for a happy-path foreground grab."""
    window = MagicMock()
    window.winId.return_value = hwnd

    user32 = MagicMock()
    user32.IsIconic.return_value = False
    user32.GetForegroundWindow.return_value = fg_hwnd
    user32.GetWindowThreadProcessId.return_value = 2000
    user32.AttachThreadInput.return_value = 1

    kernel32 = MagicMock()
    kernel32.GetCurrentThreadId.return_value = 1000
    return window, kernel32, user32


def test_calls_setforegroundwindow():
    """Happy path: SetForegroundWindow is called with the window's HWND."""
    window, kernel32, user32 = _make_mocks()
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)
    user32.SetForegroundWindow.assert_called_once_with(0xABCD)


def test_attaches_and_detaches_thread_input():
    """The foreground-lock bypass attaches (True) then detaches (False)."""
    window, kernel32, user32 = _make_mocks()
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)
    assert user32.AttachThreadInput.call_args_list == [
        call(1000, 2000, True),
        call(1000, 2000, False),
    ]


def test_qt_activation_invoked():
    """The cross-platform Qt layer raises and activates the window."""
    window, kernel32, user32 = _make_mocks()
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)
    window.raise_.assert_called_once()
    window.activateWindow.assert_called_once()


def test_flashes_when_foreground_denied():
    """OS still has a different foreground window → FlashWindowEx fires."""
    window, kernel32, user32 = _make_mocks(fg_hwnd=0x9999)   # != hwnd
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)
    user32.FlashWindowEx.assert_called_once()


def test_no_flash_when_foreground_succeeds():
    """Window is now foreground → no taskbar flash."""
    window, kernel32, user32 = _make_mocks(fg_hwnd=0xABCD)   # == hwnd
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)
    user32.FlashWindowEx.assert_not_called()


def test_no_hwnd_is_noop():
    """winId() == 0 → bail out before any foreground call."""
    window, kernel32, user32 = _make_mocks(hwnd=0)
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)
    user32.SetForegroundWindow.assert_not_called()


def test_exception_is_silent():
    """Any Win32 exception is swallowed — bring_to_foreground never raises."""
    window, kernel32, user32 = _make_mocks()
    user32.SetForegroundWindow.side_effect = Exception("win32 exploded")
    with patch('ctypes.windll') as windll:
        windll.kernel32 = kernel32
        windll.user32   = user32
        bring_to_foreground(window)   # must not raise
