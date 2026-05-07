"""Verifies AnimatedProgressBar's dual-mode sink behavior.

CLI mode (no sink): the threaded ANSI plasma-sweep keeps writing to
stdout — the Week 6 visual we don't want to regress.

GUI mode (sink installed): the animation thread is *not* started, and
update()/finish() emit (percent, label) tuples via the sink. This is
what stops `\r\x1b[K[█▓▒░]` escape garbage from leaking into the
output_panel widget during fix execution.
"""

from __future__ import annotations

import io
import sys
from contextlib import redirect_stdout

from src.utils import progress_bar
from src.utils.progress_bar import AnimatedProgressBar


def test_gui_mode_emits_percent_and_label():
    captured: list[tuple[int, str]] = []
    progress_bar.set_progress_sink(lambda pct, msg: captured.append((pct, msg)))
    try:
        bar = AnimatedProgressBar(total=4, label="Applying fixes")
        bar.start()
        bar.update(1, "Setting refresh rate")
        bar.update(2, "Switching power plan")
        bar.update(4, "Cleaning temp")
        bar.finish()
    finally:
        progress_bar.set_progress_sink(None)

    percentages = [pct for pct, _ in captured]
    assert percentages == [0, 25, 50, 100, 100]
    assert captured[1][1] == "Setting refresh rate"
    assert captured[-1][0] == 100


def test_gui_mode_does_not_start_animation_thread():
    progress_bar.set_progress_sink(lambda pct, msg: None)
    try:
        bar = AnimatedProgressBar(total=2, label="x")
        bar.start()
        try:
            assert bar._thread is None
            assert bar._running is False
        finally:
            bar.finish()
    finally:
        progress_bar.set_progress_sink(None)


def test_cli_mode_falls_back_to_ansi_animation(monkeypatch):
    """No sink installed → original threading + stdout writes still happen."""
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True, raising=False)
    buf = io.StringIO()
    with redirect_stdout(buf):
        bar = AnimatedProgressBar(total=2, label="cli")
        bar.start()
        bar.update(1, "step")
        bar.update(2, "done")
        bar.finish()
    output = buf.getvalue()
    assert "\r" in output, "CLI mode must still emit carriage-return redraws"
    assert "cli" in output


def test_set_progress_sink_clears_to_none(monkeypatch):
    progress_bar.set_progress_sink(lambda pct, msg: None)
    progress_bar.set_progress_sink(None)
    assert progress_bar._PROGRESS_SINK is None
