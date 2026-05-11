"""QSplashScreen for the 3-9 sec cold-start gap.

The brand mark + status updates close the trust gap that would otherwise
burn first-run users on an admin-elevated tool. Per Design Review the
brand voice tagline lives here ("the friend who knows computers") while
the step status messages stay utility ("Initializing UI…", "Starting
thermal monitor…", "Ready.").
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen


_SPLASH_W = 480
_SPLASH_H = 320


def make_splash() -> QSplashScreen:
    """Return a styled splash screen ready for ``show()``."""
    pixmap = QPixmap(_SPLASH_W, _SPLASH_H)
    pixmap.fill(QColor("#2E2F3A"))  # elevated

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Brand mark — JetBrains Mono Bold in accent cyan.
        brand_font = QFont("JetBrains Mono", 36, QFont.Weight.Bold)
        painter.setFont(brand_font)
        painter.setPen(QColor("#00E5CC"))
        painter.drawText(
            pixmap.rect().adjusted(0, -32, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "lil_bro",
        )

        # Tagline — DM Sans, secondary text color (brand voice).
        tagline_font = QFont("DM Sans", 11)
        painter.setFont(tagline_font)
        painter.setPen(QColor("#9B9AA0"))
        painter.drawText(
            pixmap.rect().adjusted(0, 80, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "the friend who knows computers",
        )
    finally:
        painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.setObjectName("splash")
    update_splash(splash, "Loading…")
    return splash


def update_splash(splash: QSplashScreen, message: str) -> None:
    """Show a status update along the splash bottom."""
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#9B9AA0"),
    )


def show_splash_error(splash: QSplashScreen, message: str) -> None:
    """Render an error-state status (coral) when a startup step fails."""
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#FF6B6B"),
    )
