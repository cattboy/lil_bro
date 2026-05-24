"""Interactive QSS: buttons, sidebar nav, log toolbar, status bar widget."""

from __future__ import annotations

from src.gui.theme.tokens import FONTS


def _qss_buttons(c: dict[str, str]) -> str:
    """QPushButton base style and the primary/warning/secondary variants."""
    return f"""
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
"""


def _qss_sidebar(c: dict[str, str]) -> str:
    """V2 sidebar: brand label, nav items with state variants, nav divider."""
    return f"""
    /* ================================================================
       V2 COMPONENTS
       ================================================================ */

    /* --- Sidebar brand label ----------------------------------------- */
    QLabel#sidebarBrand {{
        font-family: "{FONTS["mono"]}";
        font-size: 16px;
        font-weight: 800;
        color: {c["text_primary"]};
        padding: 0px 12px 16px 12px;
        letter-spacing: -0.02em;
    }}

    /* --- Sidebar nav items ------------------------------------------- */
    QPushButton[navRole="nav"] {{
        background-color: transparent;
        color: {c["text_secondary"]};
        border: none;
        border-left: 2px solid transparent;
        border-radius: 0px;
        padding: 9px 14px;
        text-align: left;
        font-size: 13px;
        font-weight: 400;
    }}
    QPushButton[navRole="nav"]:hover {{
        background-color: {c["hover"]};
        color: {c["text_primary"]};
    }}
    QPushButton[navState="active"] {{
        background-color: {c["accent_dim"]};
        color: {c["text_primary"]};
        border-left: 2px solid {c["accent"]};
        font-weight: 500;
    }}
    QPushButton[navState="active"]:hover {{
        background-color: {c["accent_dim"]};
    }}
    QPushButton[navState="muted"] {{
        color: {c["text_muted"]};
        font-size: 12px;
    }}
    QPushButton[navState="warning"] {{
        color: {c["warning"]};
    }}
    QPushButton[navState="warning"]:hover {{
        background-color: rgba(255, 181, 71, 0.08);
        color: {c["warning"]};
    }}
    QPushButton[navState="danger"] {{
        color: {c["error"]};
    }}
    QPushButton[navState="danger"]:hover {{
        background-color: rgba(255, 107, 107, 0.08);
        color: {c["error"]};
    }}

    /* Nav divider */
    QFrame#navDivider {{
        background-color: {c["border_default"]};
        border: none;
        max-height: 1px;
        margin: 4px 12px;
    }}
"""


def _qss_log_toolbar(c: dict[str, str]) -> str:
    """Log panel toolbar, title, and toolbar buttons."""
    return f"""
    /* --- Log toolbar ------------------------------------------------- */
    QFrame#logToolbar {{
        background-color: {c["elevated"]};
        border: none;
        border-bottom: 1px solid {c["border_default"]};
        border-radius: 0px;
        padding: 0px;
    }}
    QLabel#logToolbarTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        letter-spacing: 0.10em;
        color: {c["text_muted"]};
        padding: 8px 12px;
    }}
    QPushButton[logBtn="true"] {{
        background-color: transparent;
        color: {c["text_secondary"]};
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 11px;
        font-family: "{FONTS["mono"]}";
    }}
    QPushButton[logBtn="true"]:hover {{
        background-color: {c["hover"]};
        color: {c["text_primary"]};
    }}
"""


def _qss_status_bar(c: dict[str, str]) -> str:
    """Custom bottom status bar widget: dot, label, separator."""
    return f"""
    /* --- Custom status bar widget ------------------------------------ */
    QWidget#statusBarWidget {{
        background-color: {c["elevated"]};
        border-top: 1px solid {c["border_default"]};
    }}
    QLabel#sbDot {{
        font-size: 8px;
        color: {c["success"]};
    }}
    QLabel#sbDot[dotState="run"] {{
        color: {c["accent"]};
    }}
    QLabel#sbLabel {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        color: {c["text_secondary"]};
    }}
    QLabel#sbSep {{
        font-size: 11px;
        color: {c["border_default"]};
    }}
"""
