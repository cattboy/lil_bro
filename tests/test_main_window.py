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
