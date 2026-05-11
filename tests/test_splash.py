"""Verifies the QSplashScreen renders, accepts status updates, and shows error states."""

from __future__ import annotations

from PySide6.QtWidgets import QSplashScreen

from src.gui.widgets.splash import make_splash, show_splash_error, update_splash


def test_make_splash_returns_qsplashscreen(qtbot):
    splash = make_splash()
    qtbot.addWidget(splash)
    assert isinstance(splash, QSplashScreen)
    assert splash.objectName() == "splash"
    pixmap = splash.pixmap()
    assert pixmap is not None
    assert pixmap.width() > 0


def test_update_splash_changes_message(qtbot):
    splash = make_splash()
    qtbot.addWidget(splash)
    update_splash(splash, "Starting thermal monitor…")
    assert "thermal monitor" in splash.message().lower()


def test_show_splash_error_changes_message(qtbot):
    splash = make_splash()
    qtbot.addWidget(splash)
    show_splash_error(splash, "Continue without thermal monitor?")
    assert "thermal monitor" in splash.message().lower()
