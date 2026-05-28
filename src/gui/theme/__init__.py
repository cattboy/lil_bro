"""DESIGN.md → QSS bridge package.

Public surface is unchanged from the former single-module ``theme.py`` —
``COLORS``, ``FONTS``, ``build_stylesheet``, ``repolish``, ``load_fonts`` — so
every ``from src.gui.theme import ...`` / ``from src.gui import theme`` consumer
keeps resolving. See ``tokens.py`` for the token-assignment reference table.
"""

from __future__ import annotations

from src.gui.theme.helpers import load_fonts, repolish
from src.gui.theme.stylesheet import build_stylesheet
from src.gui.theme.tokens import COLORS, FONTS

__all__ = [
    "COLORS",
    "FONTS",
    "build_stylesheet",
    "load_fonts",
    "repolish",
]
