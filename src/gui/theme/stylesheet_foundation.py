"""Foundation QSS: base surfaces, window chrome, text displays."""

from __future__ import annotations

from src.gui.theme.tokens import FONTS


def _qss_base(c: dict[str, str]) -> str:
    """Base surfaces: windows, sidebar frame, cards, phase-card status states."""
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
"""


def _qss_text(c: dict[str, str]) -> str:
    """Text edits, labels, semantic status labels, progress label."""
    return f"""
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

    /* Semantic status labels */
    QLabel#statusSuccess {{ color: {c["success"]}; }}
    QLabel#statusWarning {{ color: {c["warning"]}; }}
    QLabel#statusError   {{ color: {c["error"]}; }}
    QLabel#statusInfo    {{ color: {c["info"]}; }}

    QLabel#progressLabel {{
        color: {c["text_secondary"]};
        font-size: 12px;
    }}
"""


def _qss_chrome(c: dict[str, str]) -> str:
    """Window chrome: status bar, progress bars, scroll bars, splitter."""
    return f"""
    /* --- Chrome ------------------------------------------------------ */
    QStatusBar {{
        background-color: {c["elevated"]};
        color: {c["text_muted"]};
        border-top: 1px solid {c["border_default"]};
    }}

    QProgressBar {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 9999px;
        text-align: center;
        color: {c["text_primary"]};
    }}
    QProgressBar::chunk {{
        background-color: {c["accent"]};
        border-radius: 9999px;
    }}
    QProgressBar#splashProgress {{
        background-color: {c["border_default"]};
        border: none;
        border-radius: 2px;
    }}
    QProgressBar#splashProgress::chunk {{
        background-color: {c["accent"]};
        border-radius: 2px;
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
