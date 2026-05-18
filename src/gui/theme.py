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

    /* Semantic status labels */
    QLabel#statusSuccess {{ color: {c["success"]}; }}
    QLabel#statusWarning {{ color: {c["warning"]}; }}
    QLabel#statusError   {{ color: {c["error"]}; }}
    QLabel#statusInfo    {{ color: {c["info"]}; }}

    QLabel#progressLabel {{
        color: {c["text_secondary"]};
        font-size: 12px;
    }}

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

    /* --- Stat card tone variants ------------------------------------- */
    QFrame#dashboardCard[statTone="norm"] {{
        border: 1px solid {c["border_default"]};
    }}
    QFrame#dashboardCard[statTone="warn"] {{
        border: 1px solid rgba(255, 181, 71, 0.5);
    }}
    QFrame#dashboardCard[statTone="ok"] {{
        border: 1px solid rgba(74, 222, 128, 0.5);
    }}
    QFrame#dashboardCard[statTone="cyan"] {{
        border: 1px solid {c["border_accent"]};
    }}
    QLabel#cardValue[statTone="warn"] {{
        color: {c["warning"]};
    }}
    QLabel#cardValue[statTone="ok"] {{
        color: {c["success"]};
    }}
    QLabel#cardValue[statTone="cyan"] {{
        color: {c["accent"]};
    }}

    /* --- Chart wrap -------------------------------------------------- */
    QFrame#chartWrap {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 8px;
        padding: 0px;
    }}
    QFrame#chartHeader {{
        background-color: transparent;
        border: none;
        padding: 12px 16px 8px 16px;
    }}
    QLabel#chartTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.10em;
        text-transform: uppercase;
        color: {c["text_muted"]};
    }}
    QLabel#legendCpu {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        color: {c["accent"]};
    }}
    QLabel#legendGpu {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        color: #D183E8;
    }}

    /* --- USB Polling widget ------------------------------------------ */
    QFrame#pollWidget {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 8px;
        padding: 16px;
    }}
    QLabel#pollLabel {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.10em;
        color: {c["text_muted"]};
    }}
    QLabel#pollValue {{
        font-family: "{FONTS["mono"]}";
        font-size: 36px;
        font-weight: 700;
        color: {c["text_primary"]};
    }}
    QLabel#pollUnit {{
        font-family: "{FONTS["mono"]}";
        font-size: 16px;
        color: {c["text_secondary"]};
    }}
    QLabel#pollStatus {{
        font-size: 12px;
        color: {c["text_secondary"]};
    }}

    /* Severity tone variants — applied via setProperty("sev", "low" | "medium" | "high")
       on pollStatus, pollValue, and pollLabel widgets. Matches fixSev convention. */
    QLabel#pollStatus[sev="low"]    {{ color: {c["success"]}; }}
    QLabel#pollStatus[sev="medium"] {{ color: {c["warning"]}; }}
    QLabel#pollStatus[sev="high"]   {{ color: {c["error"]}; }}

    QLabel#pollValue[sev="low"]    {{ color: {c["success"]}; }}
    QLabel#pollValue[sev="medium"] {{ color: {c["warning"]}; }}
    QLabel#pollValue[sev="high"]   {{ color: {c["error"]}; }}

    QLabel#pollLabel[sev="high"]   {{ color: {c["error"]}; }}

    /* --- Phase row --------------------------------------------------- */
    QFrame#phaseRow {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 8px;
        padding: 0px;
    }}

    /* Phase cards in row are compact (no outer padding) */
    QFrame#phaseCard {{
        background-color: transparent;
        border: none;
        border-left: 1px solid {c["border_default"]};
        border-radius: 0px;
        padding: 12px 16px;
    }}
    QFrame#phaseCard:first-child {{
        border-left: none;
    }}
    QFrame#phaseCard[phaseStatus="active"] {{
        background-color: {c["accent_dim"]};
        border-left: 2px solid {c["accent"]};
    }}
    QFrame#phaseCard[phaseStatus="done"] {{
        background-color: transparent;
        border-left: 1px solid {c["border_default"]};
    }}
    QLabel#phaseNum {{
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        color: {c["text_muted"]};
        letter-spacing: 0.08em;
    }}
    QLabel#phaseName {{
        font-family: "{FONTS["mono"]}";
        font-size: 12px;
        font-weight: 600;
        color: {c["text_primary"]};
    }}
    QLabel#phaseStatus {{
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        color: {c["text_muted"]};
    }}
    QLabel#phaseStatus[phaseStatus="active"] {{
        color: {c["accent"]};
    }}
    QLabel#phaseStatus[phaseStatus="done"] {{
        color: {c["success"]};
    }}
    QLabel#phaseStatus[phaseStatus="failed"] {{
        color: {c["error"]};
    }}

    /* --- Output view header ------------------------------------------ */
    QFrame#outputHeader {{
        background-color: transparent;
        border: none;
        border-bottom: 1px solid {c["border_default"]};
        padding: 12px 20px;
    }}
    QLabel#outputTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 16px;
        font-weight: 700;
        color: {c["text_primary"]};
    }}

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

    /* --- Approval (batch) dialog ------------------------------------- */
    QDialog#batchDialog {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 12px;
    }}
    QLabel#dlgTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 16px;
        font-weight: 700;
        color: {c["text_primary"]};
    }}
    QLabel#dlgSubtitle {{
        font-size: 13px;
        color: {c["text_secondary"]};
    }}
    QFrame#fixItem {{
        background-color: {c["elevated"]};
        border: 1px solid {c["border_default"]};
        border-radius: 8px;
        padding: 12px;
    }}
    QFrame#fixItem[selected="true"] {{
        border: 1px solid {c["border_accent"]};
        background-color: rgba(0, 229, 204, 0.05);
    }}
    QLabel#fixSev[sev="high"] {{
        color: {c["error"]};
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.08em;
    }}
    QLabel#fixSev[sev="medium"] {{
        color: {c["warning"]};
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.08em;
    }}
    QLabel#fixSev[sev="low"] {{
        color: {c["success"]};
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        font-weight: 600;
        letter-spacing: 0.08em;
    }}
    QLabel#fixTitle {{
        font-size: 13px;
        font-weight: 600;
        color: {c["text_primary"]};
    }}
    QLabel#fixDesc {{
        font-size: 12px;
        color: {c["text_secondary"]};
    }}
    QLabel#modeBadge[mode="AUTO"] {{
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        font-weight: 600;
        color: {c["accent"]};
        background-color: {c["accent_dim"]};
        border: 1px solid {c["border_accent"]};
        border-radius: 4px;
        padding: 2px 6px;
    }}
    QLabel#modeBadge[mode="MANUAL"] {{
        font-family: "{FONTS["mono"]}";
        font-size: 10px;
        font-weight: 600;
        color: {c["text_secondary"]};
        background-color: {c["hover"]};
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        padding: 2px 6px;
    }}
    QLabel#checkBox {{
        font-family: "{FONTS["mono"]}";
        font-size: 14px;
        font-weight: 600;
        color: {c["accent"]};
        min-width: 20px;
        min-height: 20px;
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        padding: 1px 4px;
    }}
    QLabel#checkBox[checked="false"] {{
        color: {c["text_muted"]};
        border: 1px solid {c["border_default"]};
    }}

    /* --- Confirm dialog visual update -------------------------------- */
    QLabel#confirmIcon {{
        font-size: 28px;
        color: {c["accent"]};
    }}
    QLabel#confirmTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 14px;
        font-weight: 600;
        color: {c["text_primary"]};
    }}
    QLabel#confirmDesc {{
        font-size: 12px;
        color: {c["text_muted"]};
        line-height: 1.5;
    }}

    /* --- Splash dialog ----------------------------------------------- */
    QDialog#splashDialog {{
        background-color: {c["deep"]};
    }}
    QLabel#splashBrand {{
        font-family: "{FONTS["mono"]}";
        font-size: 48px;
        font-weight: 800;
        color: {c["text_primary"]};
        letter-spacing: -0.02em;
    }}
    QLabel#splashBrandAccent {{
        font-family: "{FONTS["mono"]}";
        font-size: 48px;
        font-weight: 800;
        color: {c["accent"]};
        letter-spacing: -0.02em;
    }}
    QLabel#splashTagline {{
        font-size: 14px;
        color: {c["text_secondary"]};
    }}
    QLabel#splashBadge {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        color: {c["text_muted"]};
        border: 1px solid {c["border_default"]};
        border-radius: 9999px;
        padding: 3px 10px;
    }}
    QLabel#splashStepIcon {{
        font-family: "{FONTS["mono"]}";
        font-size: 13px;
        min-width: 16px;
    }}
    QLabel#splashStepIcon[stepState="done"] {{
        color: {c["success"]};
    }}
    QLabel#splashStepIcon[stepState="run"] {{
        color: {c["accent"]};
    }}
    QLabel#splashStepIcon[stepState="pending"] {{
        color: {c["text_muted"]};
    }}
    QLabel#splashStepLabel {{
        font-size: 13px;
        color: {c["text_secondary"]};
    }}
    QLabel#splashStepResult {{
        font-family: "{FONTS["mono"]}";
        font-size: 11px;
        color: {c["text_muted"]};
        min-width: 28px;
    }}
    QLabel#splashStepResult[stepState="done"] {{
        color: {c["success"]};
    }}
    QLabel#splashStepResult[stepState="run"] {{
        color: {c["accent"]};
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
