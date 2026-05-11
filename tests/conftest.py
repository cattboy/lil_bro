"""Shared pytest fixtures for lil_bro tests.

- Forces Qt to use the offscreen platform plugin so widget tests don't need a
  real display. Must be set before any PySide6 import.
- Resets the formatting handler registry between tests so swap-after-import
  fixtures from GUI tests don't leak into other suites.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(autouse=True)
def _reset_formatting_handlers():
    """Restore formatting.py default sink + handlers between tests.

    GUI tests install Qt-backed handlers via ``set_default_sink`` /
    ``set_approval_handler`` / ``set_confirm_handler`` /
    ``set_progress_sink``. Without this fixture those swaps leak into the
    next test and the CLI-mode regression suite (``test_cli_unchanged.py``)
    starts misbehaving in unexpected ways.
    """
    try:
        from src.utils import formatting
    except ImportError:
        yield
        return

    snapshot = (
        getattr(formatting, "_DEFAULT_SINK", None),
        getattr(formatting, "_APPROVAL_HANDLER", None),
        getattr(formatting, "_CONFIRM_HANDLER", None),
    )
    yield
    if hasattr(formatting, "_DEFAULT_SINK"):
        formatting._DEFAULT_SINK = snapshot[0]
    if hasattr(formatting, "_APPROVAL_HANDLER"):
        formatting._APPROVAL_HANDLER = snapshot[1]
    if hasattr(formatting, "_CONFIRM_HANDLER"):
        formatting._CONFIRM_HANDLER = snapshot[2]

    try:
        from src.utils import progress_bar
    except ImportError:
        return
    if hasattr(progress_bar, "_PROGRESS_SINK"):
        progress_bar._PROGRESS_SINK = None
