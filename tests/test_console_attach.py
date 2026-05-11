"""Verifies console_attach.attach() Win32 logic with mocked kernel32 calls.

The actual AttachConsole / AllocConsole APIs only work on Windows with a
real console session. We mock the kernel32 surface to assert the call
order and the AllocConsole fallback path.

Properties under test:
- AttachConsole(ATTACH_PARENT_PROCESS=-1) is tried first.
- If AttachConsole returns 0 (no parent console), AllocConsole is called.
- If both fail, the function returns silently (no crash).
- When stdio is already a real tty, attach() is a no-op (development run).
- On non-Windows, attach() is a no-op even if ctypes would be importable.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from src import console_attach


def _detached_stdout():
    fake = MagicMock()
    fake.isatty.return_value = False
    return fake


@pytest.fixture
def fake_kernel32(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(sys, "stdout", _detached_stdout())
    rebind = MagicMock()
    monkeypatch.setattr(console_attach, "_rebind_stdio", rebind)

    fake_ctypes = MagicMock()
    fake_ctypes.windll.kernel32 = MagicMock()
    with patch.dict(sys.modules, {"ctypes": fake_ctypes}):
        yield fake_ctypes.windll.kernel32, rebind


def test_attach_calls_attach_console_first_then_rebinds(fake_kernel32):
    kernel32, rebind = fake_kernel32
    kernel32.AttachConsole.return_value = 1  # success
    console_attach.attach()
    kernel32.AttachConsole.assert_called_once_with(console_attach.ATTACH_PARENT_PROCESS)
    kernel32.AllocConsole.assert_not_called()
    rebind.assert_called_once()


def test_attach_falls_back_to_alloc_console(fake_kernel32):
    kernel32, rebind = fake_kernel32
    kernel32.AttachConsole.return_value = 0  # no parent console
    kernel32.AllocConsole.return_value = 1
    console_attach.attach()
    kernel32.AttachConsole.assert_called_once()
    kernel32.AllocConsole.assert_called_once()
    rebind.assert_called_once()


def test_attach_silent_when_both_fail(fake_kernel32):
    kernel32, rebind = fake_kernel32
    kernel32.AttachConsole.return_value = 0
    kernel32.AllocConsole.return_value = 0
    console_attach.attach()
    rebind.assert_not_called()


def test_attach_noop_when_stdout_is_already_tty(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    fake_stdout = MagicMock()
    fake_stdout.isatty.return_value = True
    monkeypatch.setattr(sys, "stdout", fake_stdout)
    rebind = MagicMock()
    monkeypatch.setattr(console_attach, "_rebind_stdio", rebind)
    console_attach.attach()
    rebind.assert_not_called()


def test_attach_noop_on_non_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    rebind = MagicMock()
    monkeypatch.setattr(console_attach, "_rebind_stdio", rebind)
    console_attach.attach()
    rebind.assert_not_called()
