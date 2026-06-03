"""Verifies MainWindow assembles its core widgets and exposes the menu actions."""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton, QStackedWidget

from src.gui.windows.main_window import MainWindow
from src.gui.widgets.status_bar_widget import StatusBarWidget


def test_main_window_builds_with_minimum_size(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.windowTitle() == "lil_bro"
    assert window.minimumSize().width() == 1280
    assert window.minimumSize().height() == 800


def test_main_window_has_status_bar(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert isinstance(window.status_bar_widget, StatusBarWidget)


def test_main_window_run_button_uses_active_nav_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert isinstance(window._run_button, QPushButton)
    assert window._run_button.property("navRole") == "nav"
    # navState is dynamic — the run button gets the highlighted "active"
    # nav treatment when its (output) view is shown.
    window.show_output()
    assert window._run_button.property("navState") == "active"
    window.show_dashboard()
    assert window._run_button.property("navState") == ""


def test_main_window_revert_button_highlights_on_revert_page(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    # Idle resting state: the revert nav keeps its warning tint.
    assert window._revert_button.property("navState") == "warning"
    # Navigating to the revert page lights it up like the other page nav.
    window.show_revert()
    assert window._revert_button.property("navState") == "active"
    assert window._nav_dashboard.property("navState") == ""
    # Leaving restores the warning tint, not a blank state.
    window.show_dashboard()
    assert window._revert_button.property("navState") == "warning"
    assert window._nav_dashboard.property("navState") == "active"


def test_main_window_actions_wired(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    for attr in ("_run_button", "_revert_button",
                 "_ai_setup_button", "_nav_exit"):
        assert isinstance(getattr(window, attr), QPushButton), \
            f"missing sidebar button: {attr}"


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
    (e.g. a ConfirmDialog whose own Esc dismiss handler stays intact),
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


# ── Page-nav number hotkeys (1 = Dashboard, 2 = Start Optimization) ───────────

def test_nav_shortcuts_use_window_scope(qtbot):
    """1 and 2 are bound with WindowShortcut scope so modals keep their digits.

    A modal BatchSelectionDialog owns digits 1-9 for fix selection; nav
    shortcuts must not be application-wide or they would steal those keys.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    assert len(window._nav_shortcuts) == 2
    bound = set()
    for shortcut in window._nav_shortcuts:
        assert shortcut.context() == Qt.ShortcutContext.WindowShortcut
        for key in (Qt.Key.Key_1, Qt.Key.Key_2):
            if (shortcut.key().matches(QKeySequence(key))
                    == QKeySequence.SequenceMatch.ExactMatch):
                bound.add(key)
    assert bound == {Qt.Key.Key_1, Qt.Key.Key_2}


def test_nav_shortcut_1_shows_dashboard(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    window.show_output()
    assert window._content.currentIndex() == MainWindow.OUTPUT_INDEX
    shortcut = next(
        s for s in window._nav_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_1))
        == QKeySequence.SequenceMatch.ExactMatch
    )
    shortcut.activated.emit()
    assert window._content.currentIndex() == MainWindow.DASHBOARD_INDEX


def test_nav_shortcut_2_shows_output(qtbot):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence
    window = MainWindow()
    qtbot.addWidget(window)
    assert window._content.currentIndex() == MainWindow.DASHBOARD_INDEX
    shortcut = next(
        s for s in window._nav_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_2))
        == QKeySequence.SequenceMatch.ExactMatch
    )
    shortcut.activated.emit()
    assert window._content.currentIndex() == MainWindow.OUTPUT_INDEX


def test_nav_buttons_show_number_hints(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert "(1)" in window._nav_dashboard.text()
    assert "(2)" in window._run_button.text()


def test_action_shortcuts_use_window_scope(qtbot):
    """R/E/A are bound with WindowShortcut scope so modals keep those letters."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence

    window = MainWindow()
    qtbot.addWidget(window)

    assert len(window._action_shortcuts) == 3
    bound = set()
    for shortcut in window._action_shortcuts:
        assert shortcut.context() == Qt.ShortcutContext.WindowShortcut
        for key in (Qt.Key.Key_R, Qt.Key.Key_E, Qt.Key.Key_A):
            if shortcut.key().matches(QKeySequence(key)) == QKeySequence.SequenceMatch.ExactMatch:
                bound.add(key)
    assert bound == {Qt.Key.Key_R, Qt.Key.Key_E, Qt.Key.Key_A}


def test_action_buttons_show_letter_hints(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert "(R)" in window._revert_button.text()
    assert "(A)" in window._ai_setup_button.text()
    assert "(E)" in window._nav_exit.text()


def test_revert_hotkey_navigates_when_not_on_revert_page(qtbot):
    """First R press (from another page) routes to the Revert page."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeySequence

    window = MainWindow()
    qtbot.addWidget(window)
    window.show_dashboard()
    assert window._content.currentIndex() != window.REVERT_INDEX

    shortcut = next(
        s for s in window._action_shortcuts
        if s.key().matches(QKeySequence(Qt.Key.Key_R)) == QKeySequence.SequenceMatch.ExactMatch
    )
    shortcut.activated.emit()
    assert window._content.currentIndex() == window.REVERT_INDEX


def test_revert_hotkey_triggers_revert_when_on_revert_page(qtbot):
    """Second R press (already on Revert page) drives the in-page revert button.

    No extra confirm is stacked here -- the revert flow's own prompt_approval
    ("Revert N change(s)?") is the single confirmation.
    """
    window = MainWindow()
    qtbot.addWidget(window)
    window.show_revert()

    fired = []
    window._revert_view.revert_requested.connect(lambda: fired.append(True))

    window._on_revert_hotkey()
    assert fired == [True]


def test_exit_hotkey_confirm_gates_close(qtbot):
    """E shows a confirm; close() only fires when the dialog is accepted."""
    from unittest.mock import patch

    window = MainWindow()
    qtbot.addWidget(window)

    with patch.object(window, "close") as mock_close:
        with patch("src.gui.widgets.confirm_dialog.ConfirmDialog.exec", return_value=False):
            window._on_exit_requested()
        mock_close.assert_not_called()

        with patch("src.gui.widgets.confirm_dialog.ConfirmDialog.exec", return_value=True):
            window._on_exit_requested()
        mock_close.assert_called_once()
