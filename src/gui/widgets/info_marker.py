"""Small circular "?" info marker with a hover flyout.

A reusable hover-help affordance: a tiny circular "?" chip that shows a
styled rich-text tooltip (the app's "flyout") on mouse hover. Used on the
dashboard's CPU/GPU temperature stat cards and the mouse-polling card to
explain what good/bad values look like at idle vs under load.

The tooltip copy reuses ``tooltip_html`` from ``coachmarks`` (accent-coloured
title + body, max-width 280px) so hover-help reads identically to the
first-run coachmark tooltips — imported lazily to keep this generic widget
free of an import-time dependency on the onboarding tour. The flyout chrome
(surface background, brand border) comes from the global ``QToolTip`` QSS rule
in ``stylesheet_foundation``; the "?" chip itself is styled via the
``QLabel#infoMarker`` rule in ``stylesheet_monitoring``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QLabel, QToolTip


class InfoMarker(QLabel):
    """A small circular "?" chip whose tooltip is a hover flyout."""

    # Show the flyout this many ms after the cursor enters — snappier than
    # Qt's global ~700ms tooltip wake-up delay, and scoped to this widget.
    _SHOW_DELAY_MS = 300

    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__("?", parent)
        self.setObjectName("infoMarker")
        self.setFixedSize(16, 16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        # Single-shot timer drives the early flyout; armed on hover-enter,
        # cancelled on hover-leave.
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.timeout.connect(self._show_flyout)
        self.set_help(title, body)

    def set_help(self, title: str, body: str) -> None:
        """Set/replace the hover-flyout copy (accent title + body)."""
        from src.gui.widgets.coachmarks import tooltip_html

        self.setToolTip(tooltip_html(title, body))
        self.setAccessibleName(f"{title} info")
        self.setAccessibleDescription(body)

    # ── Hover flyout (custom ~300ms delay) ──────────────────────────────

    def enterEvent(self, event) -> None:
        # Arm the short-delay timer; _show_flyout fires only if still hovered.
        self._hover_timer.start(self._SHOW_DELAY_MS)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_timer.stop()
        QToolTip.hideText()
        super().leaveEvent(event)

    def _show_flyout(self) -> None:
        # underMouse() guards a stale fire; rect() lets Qt auto-hide the tip
        # once the cursor leaves the chip. setToolTip() text stays the source.
        if self.underMouse():
            QToolTip.showText(QCursor.pos(), self.toolTip(), self, self.rect())
