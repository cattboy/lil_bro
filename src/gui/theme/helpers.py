"""Runtime theme helpers: stylesheet ``repolish`` and bundled font loading."""

from __future__ import annotations

from pathlib import Path


def repolish(widget) -> None:
    """Re-apply QSS to a widget after a dynamic property change.

    Qt does not refresh the stylesheet automatically when a property used in a
    QSS selector (e.g. ``[sev="high"]``) changes at runtime — callers must ask
    the style to re-evaluate. This wraps the unpolish/polish dance so widget
    code can stay a single line.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def load_fonts() -> None:
    """Register bundled JetBrains Mono + DM Sans .ttf files with QFontDatabase.

    No-op if the ``resources/fonts/`` directory isn't bundled (development
    runs on a machine without the .ttf files) — Qt then falls back to the
    closest available system font.
    """
    from PySide6.QtGui import QFontDatabase

    fonts_dir = _resources_dir() / "fonts"
    if not fonts_dir.is_dir():
        return
    for ttf in fonts_dir.glob("*.ttf"):
        QFontDatabase.addApplicationFont(str(ttf))


def _resources_dir() -> Path:
    """Return the bundled resources directory next to the ``src/`` tree.

    This module lives at ``src/gui/theme/helpers.py`` — four ``parent`` hops
    reach the project root (one deeper than the former ``src/gui/theme.py``).
    """
    return Path(__file__).resolve().parent.parent.parent.parent / "resources"
