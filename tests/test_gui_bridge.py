"""Verifies GuiBridge install/restore + deliver_answer cross-thread plumbing."""

from __future__ import annotations

from PySide6.QtCore import QTimer

from src.gui.bridge import GuiBridge
from src.gui.signals import PipelineSignals
from src.utils import formatting, progress_bar


def test_install_swaps_handlers_and_sinks(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    try:
        bridge.install()
        assert bridge.installed
        assert formatting._DEFAULT_SINK == bridge._emit_output
        assert formatting._APPROVAL_HANDLER == bridge._handle_approval
        assert formatting._CONFIRM_HANDLER == bridge._handle_confirm
        assert formatting._BENCHMARK_SCORE_SINK == bridge._emit_benchmark_score
        assert progress_bar._PROGRESS_SINK == bridge._emit_progress
    finally:
        bridge.restore()


def test_restore_clears_handlers_and_sinks(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    bridge.install()
    bridge.restore()
    assert not bridge.installed
    assert formatting._DEFAULT_SINK is None
    assert formatting._APPROVAL_HANDLER is None
    assert formatting._CONFIRM_HANDLER is None
    assert formatting._BENCHMARK_SCORE_SINK is None
    assert progress_bar._PROGRESS_SINK is None


def test_output_sink_emits_signal(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    bridge.install()
    try:
        with qtbot.waitSignal(signals.output_emitted, timeout=1000) as blocker:
            formatting.print_info("hello world")
        assert "hello world" in blocker.args[0]
    finally:
        bridge.restore()


def test_progress_sink_emits_signal(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    bridge.install()
    try:
        with qtbot.waitSignal(signals.progress_changed, timeout=1000) as blocker:
            progress_bar._PROGRESS_SINK(42, "step")
        assert blocker.args == [42, "step"]
    finally:
        bridge.restore()


def test_handle_approval_blocks_until_deliver_answer(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    bridge.install()
    try:
        # Connect approval_requested → simulate dialog click via deliver_answer.
        signals.approval_requested.connect(
            lambda _action: QTimer.singleShot(50, lambda: bridge.deliver_answer(True))
        )
        result = bridge._handle_approval("apply registry change")
        assert result is True
    finally:
        bridge.restore()


def test_handle_approval_safe_default_on_deny(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    bridge.install()
    try:
        signals.approval_requested.connect(
            lambda _action: QTimer.singleShot(50, lambda: bridge.deliver_answer(False))
        )
        result = bridge._handle_approval("denied action")
        assert result is False
    finally:
        bridge.restore()


def test_handle_confirm_propagates_yes(qtbot):
    signals = PipelineSignals()
    bridge = GuiBridge(signals)
    bridge.install()
    try:
        signals.confirm_requested.connect(
            lambda _q: QTimer.singleShot(50, lambda: bridge.deliver_answer(True))
        )
        assert bridge._handle_confirm("ok?") is True
    finally:
        bridge.restore()
