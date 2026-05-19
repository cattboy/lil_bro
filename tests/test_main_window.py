"""Verifies MainWindow assembles its core widgets and exposes the menu actions."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QStackedWidget, QStatusBar

from src.gui.windows.main_window import MainWindow


def test_main_window_builds_with_minimum_size(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "lil_bro"
    assert window.minimumSize().width() == 1024
    assert window.minimumSize().height() == 720


def test_main_window_has_status_bar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert isinstance(window.statusBar(), QStatusBar)
    assert "lil_bro" in window.statusBar().currentMessage()


def test_main_window_run_button_uses_primary_object_name(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert isinstance(window._run_button, QPushButton)
    assert window._run_button.objectName() == "primary"


def test_main_window_actions_wired(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    for attr in ("action_run_pipeline", "action_ai_setup",
                 "action_revert", "action_exit"):
        assert hasattr(window, attr), f"missing menu action: {attr}"


def test_main_window_view_toggle(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    stack = window._content
    assert isinstance(stack, QStackedWidget)
    assert stack.currentIndex() == MainWindow.DASHBOARD_INDEX
    window.show_output()
    assert stack.currentIndex() == MainWindow.OUTPUT_INDEX
    window.show_dashboard()
    assert stack.currentIndex() == MainWindow.DASHBOARD_INDEX


def test_main_window_accessible_name_set(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.accessibleName() == "lil_bro main window"



# ── Stop button + Esc/Q hotkey for cancel ─────────────────────────────────────

def test_stop_button_hidden_by_default(qtbot):
    """Stop button starts hidden because no pipeline is running at construction."""
    window = MainWindow()
    qtbot.addWidget(window)
    assert window._stop_button.isVisible() is False


def test_stop_button_visible_when_set_running_true(qtbot):
    """set_running(True) flips the Stop button visible alongside the Run-button state swap."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()  # widgets are only "visible" once the parent window is shown
    window.set_running(True)
    assert window._stop_button.isVisible() is True
    window.set_running(False)
    assert window._stop_button.isVisible() is False


def test_stop_button_emits_stop_requested_when_visible(qtbot):
    """Clicking the visible Stop button emits stop_requested exactly once."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.set_running(True)

    with qtbot.waitSignal(window.stop_requested, timeout=500) as blocker:
        window._stop_button.click()
    assert blocker.signal_triggered


def test_stop_button_click_noop_when_hidden(qtbot):
    """_on_stop_clicked is a no-op when the Stop button is hidden (pipeline idle).

    Esc/Q QShortcuts fire regardless of button visibility, so the handler
    must gate on the button being visible to keep hotkeys silent at idle.
    """
    from PySide6.QtCore import QTimer
    window = MainWindow()
    qtbot.addWidget(window)
    # Pipeline is NOT running -- _stop_button.isVisible() returns False.
    # Programmatically invoke _on_stop_clicked and ensure no signal fires.
    received = []
    window.stop_requested.connect(lambda: received.append(True))
    window._on_stop_clicked()
    # Process any queued signal deliveries
    QTimer.singleShot(0, lambda: None)
    qtbot.wait(50)
    assert received == [], "stop_requested fired while button was hidden"


def test_shortcut_context_is_window_not_application(qtbot):
    """D2 regression guard: cancel shortcuts must use Qt.WindowShortcut.

    Qt.ApplicationShortcut would hijack Esc/Enter from any open modal dialog
    (e.g. ApprovalDialog whose own Esc dismiss is at approval_dialog.py:50-54),
    accidentally cancelling the pipeline when the user only meant to dismiss
    or confirm a prompt.

    Also pins the count at 4 -- the cancel hotkeys are Esc, Q, Return
    (main Enter), and Enter (numpad Enter, Key_Enter).
    """
    from PySide6.QtCore import Qt
    window = MainWindow()
    qtbot.addWidget(window)
    assert len(window._stop_shortcuts) == 4, "expected Esc + Q + Return + Enter shortcuts"
    for shortcut in window._stop_shortcuts:
        assert shortcut.context() == Qt.ShortcutContext.WindowShortcut, (
            f"shortcut context must be WindowShortcut, got {shortcut.context()}"
        )


def test_esc_shortcut_emits_stop_requested_when_running(qtbot):
    """Esc shortcut fires stop_requested while pipeline runs.

    Activates the shortcut directly via ``shortcut.activated.emit()``
    rather than ``qtbot.keyClick``. Qt's offscreen plugin (used in
    headless tests, see ``conftest.py``) does not reliably route
    keystrokes to ``WindowShortcut`` handlers, but the Qt→shortcut
    mapping is Qt's responsibility -- what this codebase owns is the
    shortcut→stop_requested wiring, which is what this test verifies.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.set_running(True)

    esc_shortcut = next(
        s for s in window._stop_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_Escape))
    )
    with qtbot.waitSignal(window.stop_requested, timeout=500) as blocker:
        esc_shortcut.activated.emit()
    assert blocker.signal_triggered


def test_q_shortcut_emits_stop_requested_when_running(qtbot):
    """Q shortcut fires stop_requested while pipeline runs (see Esc-test rationale)."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.set_running(True)

    q_shortcut = next(
        s for s in window._stop_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_Q))
    )
    with qtbot.waitSignal(window.stop_requested, timeout=500) as blocker:
        q_shortcut.activated.emit()
    assert blocker.signal_triggered



def test_return_shortcut_emits_stop_requested_when_running(qtbot):
    """Return (main Enter key) fires stop_requested while pipeline runs.

    Matches the CLI's Q+Enter abort combo from _keyboard_abort_watcher.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.set_running(True)

    return_shortcut = next(
        s for s in window._stop_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_Return))
    )
    with qtbot.waitSignal(window.stop_requested, timeout=500) as blocker:
        return_shortcut.activated.emit()
    assert blocker.signal_triggered


def test_enter_shortcut_emits_stop_requested_when_running(qtbot):
    """Enter (numpad Enter, Qt.Key_Enter) fires stop_requested while pipeline runs.

    Qt distinguishes Key_Return (main keyboard) from Key_Enter (numpad);
    both are bound so users on either layout get the same cancel UX.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    window.set_running(True)

    enter_shortcut = next(
        s for s in window._stop_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_Enter))
    )
    with qtbot.waitSignal(window.stop_requested, timeout=500) as blocker:
        enter_shortcut.activated.emit()
    assert blocker.signal_triggered


def test_esc_shortcut_noop_when_idle(qtbot):
    """Esc shortcut must NOT fire stop_requested when no pipeline is running.

    Activates the shortcut directly (same rationale as the running-state
    tests above -- offscreen Qt doesn't route keystrokes to WindowShortcut
    handlers reliably). What we verify: even if the shortcut fires, the
    handler's button-visibility gate keeps stop_requested silent.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    # set_running NOT called -- stop button is hidden

    esc_shortcut = next(
        s for s in window._stop_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_Escape))
    )
    received = []
    window.stop_requested.connect(lambda: received.append(True))
    esc_shortcut.activated.emit()
    qtbot.wait(50)
    assert received == [], "stop_requested fired while pipeline was idle"
