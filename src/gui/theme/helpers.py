"""Runtime theme helpers: stylesheet ``repolish`` and bundled font loading."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QPushButton


def repolish(widget) -> None:
    """Re-apply QSS to a widget after a dynamic property change.

    Qt does not refresh the stylesheet automatically when a property used in a
    QSS selector (e.g. ``[sev="high"]``) changes at runtime — callers must ask
    the style to re-evaluate. This wraps the unpolish/polish dance so widget
    code can stay a single line.
    """
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def set_apply_busy(button: QPushButton, busy: bool, busy_label: str = "Applying…") -> None:
    """Toggle a card's action button between idle and an in-flight 'busy' state.

    Touches ONLY the button's enabled-state and label -- never the card's status
    QLabel. The status label is owned by the findings/refresh path; writing the
    transient "Applying…" text there would race the fix-result handler (which
    runs before the thread-finished reset, see StartupCoordinator) and could
    clobber a freshly-applied "✓ optimal" message. Shared by every dashboard fix
    card's ``set_applying``. ``_idle_text`` round-trips the original label through
    a dynamic property so the reset restores it without the card storing state.
    """
    if busy:
        button.setProperty("_idle_text", button.text())
        button.setText(busy_label)
        button.setEnabled(False)
    else:
        button.setEnabled(True)
        prev = button.property("_idle_text")
        if prev:
            button.setText(prev)


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


def app_icon():
    """Return the lil_bro window/taskbar icon as a ``QIcon``.

    Loads ``resources/icons/lil_bro-01-classic.ico`` (multi-size .ico so
    Windows picks the right resolution for the taskbar, title bar and
    Alt-Tab). Returns a null ``QIcon`` if the file isn't present — callers
    can hand it to ``setWindowIcon`` unconditionally; Qt treats a null icon
    as "no change".
    """
    from PySide6.QtGui import QIcon

    ico = _resources_dir() / "icons" / "lil_bro-01-classic.ico"
    if not ico.is_file():
        return QIcon()
    return QIcon(str(ico))


def _resources_dir() -> Path:
    """Return the bundled resources directory next to the ``src/`` tree.

    This module lives at ``src/gui/theme/helpers.py`` — four ``parent`` hops
    reach the project root (one deeper than the former ``src/gui/theme.py``).
    """
    return Path(__file__).resolve().parent.parent.parent.parent / "resources"
