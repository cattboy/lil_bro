"""DESIGN.md → QSS bridge. Single source of truth for colors, fonts, and tokens.

Token assignment reference (kept inline so future contributors don't need
to re-derive which token lands on which surface):

    Color: deep        #1A1B23  → main window background
    Color: surface     #24252F  → cards, panels, output panel, dialog body
    Color: elevated    #2E2F3A  → sidebar, dialog title bars, splash background
    Color: hover       #363745  → card / button hover state
    Color: accent      #00E5CC  → primary buttons, active phase border, focus ring,
                                  brand mark, current dashboard tile highlight
    Color: accent_dim  rgba(0,229,204,0.15) → active sidebar item background,
                                              in-progress phase card fill
    Color: accent_glow rgba(0,229,204,0.30) → primary button + brand mark glow
    Color: success     #4ADE80  → phase complete, "AI features enabled", checks
    Color: warning     #FFB547  → thermal 75°C threshold, dashboard caution
    Color: error       #FF6B6B  → thermal 85°C threshold, phase failed, errors
    Color: text_primary   #E8E6E3 → all body text on dark surfaces (WCAG AA 14.5:1)
    Color: text_secondary #9B9AA0 → card labels, dim section titles (WCAG AA 5.1:1)
    Color: text_muted     #6B6A70 → status bar timestamps, meta text
    Color: border_default #363745 → terminal-style bordered panels
    Color: border_accent  rgba(0,229,204,0.25) → active phase border, focused inputs

AI slop guardrails (do/don't):
    ✓ DO use full borders on cards (DESIGN.md "terminal-style bordered panels")
    ✗ DON'T `border-left: 3px solid cyan` on cards (AI slop blacklist #8)
    ✓ DO left-align labels, right-align numeric values (terminal convention)
    ✗ DON'T center-align everything (AI slop blacklist #4)
    ✗ DON'T use emoji as design elements (AI slop blacklist #7); use Qt icons or text
    ✗ DON'T "Welcome to lil_bro" hero copy (AI slop blacklist #9); splash shows brand mark
    ✓ DO use scanline texture on dark surfaces (DESIGN.md line 109)
    ✓ DO use accent glow on hover/active (DESIGN.md line 108)
"""

from __future__ import annotations

from pathlib import Path


COLORS: dict[str, str] = {
    "deep":           "#1A1B23",
    "surface":        "#24252F",
    "elevated":       "#2E2F3A",
    "hover":          "#363745",
    "accent":         "#00E5CC",
    "accent_dim":     "rgba(0, 229, 204, 0.15)",
    "accent_glow":    "rgba(0, 229, 204, 0.3)",
    "success":        "#4ADE80",
    "warning":        "#FFB547",
    "error":          "#FF6B6B",
    "info":           "#60A5FA",
    "text_primary":   "#E8E6E3",
    "text_secondary": "#9B9AA0",
    "text_muted":     "#6B6A70",
    "border_default": "#363745",
    "border_accent":  "rgba(0, 229, 204, 0.25)",
}

FONTS: dict[str, str] = {
    "mono": "JetBrains Mono",
    "sans": "DM Sans",
}


def build_stylesheet() -> str:
    """Return the QSS for the entire app, with DESIGN.md tokens substituted."""
    c = COLORS
    return f"""
    /* --- Base surfaces ----------------------------------------------- */
    QMainWindow, QDialog, QWidget {{
        background-color: {c["deep"]};
        color: {c["text_primary"]};
        font-family: "{FONTS["sans"]}", sans-serif;
        font-size: 14px;
    }}

    QFrame#sidebar {{
        background-color: {c["elevated"]};
        border-right: 1px solid {c["border_default"]};
    }}

    QFrame#card,
    QFrame#dashboardCard,
    QFrame#phaseCard,
    QFrame#outputPanel {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 8px;
        padding: 16px;
    }}

    /* Phase card status states (driven by setProperty("phaseStatus", ...)) */
    QFrame#phaseCard[phaseStatus="active"] {{
        border: 1px solid {c["accent"]};
        background-color: {c["accent_dim"]};
    }}
    QFrame#phaseCard[phaseStatus="done"] {{
        border: 1px solid {c["success"]};
    }}
    QFrame#phaseCard[phaseStatus="failed"] {{
        border: 1px solid {c["error"]};
    }}

    /* --- Buttons ----------------------------------------------------- */
    QPushButton {{
        background-color: {c["surface"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        padding: 8px 16px;
    }}
    QPushButton:hover {{
        background-color: {c["hover"]};
    }}
    QPushButton#primary {{
        background-color: {c["accent"]};
        color: {c["deep"]};
        border: 1px solid {c["accent"]};
        font-weight: 600;
    }}
    QPushButton#primary:hover {{
        background-color: {c["accent"]};
        border: 1px solid {c["text_primary"]};
    }}
    QPushButton#warning {{
        background-color: rgba(255, 181, 71, 0.12);
        color: {c["warning"]};
        border: 1px solid rgba(255, 181, 71, 0.35);
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: 600;
    }}
    QPushButton#warning:hover {{
        background-color: rgba(255, 181, 71, 0.22);
        border-color: {c["warning"]};
    }}
    QPushButton#warning:disabled {{
        color: {c["text_muted"]};
        border-color: {c["border_default"]};
        background-color: transparent;
    }}
    QPushButton#secondary {{
        background-color: {c["elevated"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        padding: 8px 16px;
        font-weight: 500;
    }}
    QPushButton#secondary:hover {{
        background-color: {c["hover"]};
        border-color: {c["info"]};
    }}
    QPushButton#secondary:disabled {{
        color: {c["text_muted"]};
    }}
    QPushButton:focus {{
        border: 2px solid {c["accent"]};
    }}
    QPushButton:disabled {{
        color: {c["text_muted"]};
    }}

    /* --- Text + value displays --------------------------------------- */
    QTextEdit, QPlainTextEdit, QListView {{
        background-color: {c["surface"]};
        color: {c["text_primary"]};
        border: 1px solid {c["border_default"]};
        border-radius: 8px;
        font-family: "{FONTS["mono"]}", monospace;
        font-size: 13px;
        selection-background-color: {c["accent_dim"]};
        selection-color: {c["text_primary"]};
    }}

    QLabel {{
        background-color: transparent;
        color: {c["text_primary"]};
    }}
    QLabel#sectionHeader {{
        font-family: "{FONTS["mono"]}";
        font-weight: bold;
        font-size: 18px;
        color: {c["text_primary"]};
    }}
    QLabel#cardLabel {{
        color: {c["text_secondary"]};
        font-size: 11px;
        font-weight: 500;
    }}
    QLabel#cardValue {{
        color: {c["text_primary"]};
        font-family: "{FONTS["mono"]}";
        font-size: 24px;
        font-weight: 500;
    }}
    QLabel#brandMark {{
        color: {c["accent"]};
        font-family: "{FONTS["mono"]}";
        font-size: 56px;
        font-weight: bold;
    }}

    /* Semantic status labels — used for thermal thresholds, dashboard
       caution states, error banners, info messages. */
    QLabel#statusSuccess {{ color: {c["success"]}; }}
    QLabel#statusWarning {{ color: {c["warning"]}; }}
    QLabel#statusError   {{ color: {c["error"]}; }}
    QLabel#statusInfo    {{ color: {c["info"]}; }}

    /* --- Chrome ------------------------------------------------------ */
    QStatusBar {{
        background-color: {c["elevated"]};
        color: {c["text_muted"]};
        border-top: 1px solid {c["border_default"]};
    }}

    QProgressBar {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        text-align: center;
        color: {c["text_primary"]};
    }}
    QProgressBar::chunk {{
        background-color: {c["accent"]};
        border-radius: 3px;
    }}

    QScrollBar:vertical, QScrollBar:horizontal {{
        background-color: {c["deep"]};
        border: none;
    }}
    QScrollBar::handle:vertical, QScrollBar::handle:horizontal {{
        background-color: {c["hover"]};
        border-radius: 4px;
    }}

    QSplitter::handle {{
        background-color: {c["border_default"]};
    }}
    """


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
    """Return the bundled resources directory next to the ``src/`` tree."""
    return Path(__file__).resolve().parent.parent.parent / "resources"
