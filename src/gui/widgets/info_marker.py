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

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel


class InfoMarker(QLabel):
    """A small circular "?" chip whose tooltip is a hover flyout."""

    def __init__(self, title: str, body: str, parent=None) -> None:
        super().__init__("?", parent)
        self.setObjectName("infoMarker")
        self.setFixedSize(16, 16)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.set_help(title, body)

    def set_help(self, title: str, body: str) -> None:
        """Set/replace the hover-flyout copy (accent title + body)."""
        from src.gui.widgets.coachmarks import tooltip_html

        self.setToolTip(tooltip_html(title, body))
        self.setAccessibleName(f"{title} info")
        self.setAccessibleDescription(body)
