"""Widget smoke tests for v0.2.0.0 classes with zero prior coverage.

Uses the offscreen Qt platform (set in conftest.py). All tests avoid real
system calls — anything that touches WMI, ctypes, or subprocesses is patched.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.gui.widgets.status_bar_widget import StatusBarWidget
from src.gui.widgets.monitor_refresh_card import MonitorEmptyCard, MonitorRefreshCard


class TestStatusBarWidgetSetState:
    def test_set_state_run_updates_dot_and_label(self, qtbot):
        """set_state('run', ...) sets dotState='run' and updates the state label."""
        widget = StatusBarWidget()
        qtbot.addWidget(widget)
        with patch("src.gui.widgets.status_bar_widget.repolish"):
            widget.set_state("run", "Optimizing…")
        assert widget._state_label.text() == "Optimizing…"
        assert widget._dot.property("dotState") == "run"

    def test_set_state_idle_uses_ok_dot(self, qtbot):
        """Non-'run' state must set dotState='ok'."""
        widget = StatusBarWidget()
        qtbot.addWidget(widget)
        with patch("src.gui.widgets.status_bar_widget.repolish"):
            widget.set_state("idle", "Idle")
        assert widget._state_label.text() == "Idle"
        assert widget._dot.property("dotState") == "ok"


class TestMonitorRefreshCardSetDisplay:
    def _make_card(self, qtbot) -> MonitorRefreshCard:
        card = MonitorRefreshCard()
        qtbot.addWidget(card)
        return card

    def test_wmi_source_hides_fix_button(self, qtbot):
        """WMI-sourced display must hide the Fix button and show the WMI notice."""
        card = self._make_card(qtbot)
        with patch("src.gui.widgets.monitor_refresh_card.repolish"):
            card.set_display({"device": "WMI:Display1", "source": "wmi",
                              "current_refresh_hz": 60, "max_refresh_hz": 144})
        assert card._fix_btn.isHidden()
        assert "WMI" in card._status_lbl.text()

    def test_optimal_refresh_hides_fix_button(self, qtbot):
        """current >= max must show the checkmark status and hide the Fix button."""
        card = self._make_card(qtbot)
        with patch("src.gui.widgets.monitor_refresh_card.repolish"):
            card.set_display({"device": r"\\.\DISPLAY1",
                              "current_refresh_hz": 144, "max_refresh_hz": 144})
        assert card._fix_btn.isHidden()
        assert "✓" in card._status_lbl.text()

    def test_suboptimal_refresh_shows_fix_button(self, qtbot):
        """current < max must show the Fix button and set a proposal as status text.

        isVisible() returns False in offscreen mode when the parent is not shown;
        use not isHidden() to check the explicit show/hide state instead.
        """
        card = self._make_card(qtbot)
        with patch("src.gui.widgets.monitor_refresh_card.repolish"), \
             patch("src.gui.widgets.monitor_refresh_card.propose_for_check",
                   return_value={"proposed_action": "Increase to 144 Hz",
                                 "explanation": "Your monitor supports 144 Hz"}):
            card.set_display({"device": r"\\.\DISPLAY1",
                              "current_refresh_hz": 60, "max_refresh_hz": 144})
        assert not card._fix_btn.isHidden()
        assert card._status_lbl.text() == "Increase to 144 Hz"


class TestMonitorEmptyCard:
    def test_renders_without_crash(self, qtbot):
        """MonitorEmptyCard must construct and show without raising."""
        card = MonitorEmptyCard()
        qtbot.addWidget(card)
        card.show()
        assert card.accessibleName() == "Monitor refresh rate — no displays detected"

    def test_refresh_button_emits_signal(self, qtbot):
        """Clicking the Refresh button must emit refresh_requested."""
        card = MonitorEmptyCard()
        qtbot.addWidget(card)
        with qtbot.waitSignal(card.refresh_requested, timeout=1000):
            card._refresh_btn.click()


class TestGuiBridgeAbortPending:
    def test_abort_pending_calls_callback_with_false(self):
        """abort_pending must deliver False to any pending callback."""
        from src.gui.bridge import GuiBridge
        bridge = GuiBridge(signals=MagicMock())
        cb = MagicMock()
        bridge._answer_callback = cb
        bridge.abort_pending()
        cb.assert_called_once_with(False)

    def test_abort_pending_is_noop_when_no_callback(self):
        """abort_pending with no pending callback must not raise."""
        from src.gui.bridge import GuiBridge
        bridge = GuiBridge(signals=MagicMock())
        bridge._answer_callback = None
        bridge.abort_pending()  # must not raise
