"""QSS builder. Assembles the application stylesheet from per-component sections.

``build_stylesheet()`` joins the ``_qss_*`` section helpers below; each section
is kept small so it can be edited independently (Serena-targetable). Colors are
passed in as ``c`` (the ``COLORS`` dict); fonts are read from the module-level
``FONTS`` import.
"""

from __future__ import annotations

from src.gui.theme.tokens import COLORS, FONTS


def build_stylesheet() -> str:
    """Return the QSS for the entire app, with DESIGN.md tokens substituted."""
    c = COLORS
    return "\n".join([
        _qss_base(c),
        _qss_buttons(c),
        _qss_text(c),
        _qss_chrome(c),
        _qss_sidebar(c),
        _qss_stat_cards(c),
        _qss_chart(c),
        _qss_poll(c),
        _qss_phase_row(c),
        _qss_output_header(c),
        _qss_log_toolbar(c),
        _qss_status_bar(c),
        _qss_batch_dialog(c),
        _qss_confirm_dialog(c),
        _qss_splash(c),
    ])


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


def _qss_stat_cards(c: dict[str, str]) -> str:
    """Dashboard stat-card tone variants (statTone — distinct from sev)."""
    return f"""
    /* --- Stat card tone variants -------------------------------------
     * IMPORTANT: ''statTone'' and ''sev'' are distinct dynamic properties
     * with non-overlapping purposes — do NOT merge them.
     *
     *   statTone in {{norm, warn, ok, cyan}}
     *     Applied to dashboard stat cards (#dashboardCard, #cardValue).
     *     Encodes value identity tone (the *kind* of stat the card shows),
     *     not severity. ''norm'' = baseline border, ''cyan'' = accent identity,
     *     ''warn''/''ok'' = visual emphasis.
     *
     *   sev in {{low, medium, high}}
     *     Applied to polling widgets, fixSev badge, and severity-coded
     *     status text. Encodes user-facing severity from the audit
     *     pipeline (matches the fixSev / DESIGN.md semantic-color system).
     *
     * If a widget needs both (e.g. a card whose VALUE is severity-coded),
     * use statTone for the card chrome and sev for the inner label.
     */
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
"""


def _qss_chart(c: dict[str, str]) -> str:
    """Thermal chart wrapper, header, and CPU/GPU legend labels."""
    return f"""
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
"""


def _qss_poll(c: dict[str, str]) -> str:
    """Polling/monitor card chrome, inner labels, and sev tone variants."""
    return f"""
    /* --- USB Polling widget ------------------------------------------ */
    /* Shared chrome — same border, background, padding for poll/monitor/empty cards.
     * Inner labels (#pollLabel, #pollValue, #pollUnit, #pollStatus) are reused
     * by both MonitorRefreshCard and the original polling widget, so only the
     * frame selector needs widening. */
    QFrame#pollWidget,
    QFrame#monitorCard,
    QFrame#monitorEmptyCard {{
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
"""


def _qss_phase_row(c: dict[str, str]) -> str:
    """Pipeline phase row container and compact per-phase cards/labels."""
    return f"""
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
"""


def _qss_output_header(c: dict[str, str]) -> str:
    """Output view header bar and title label."""
    return f"""
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


def _qss_batch_dialog(c: dict[str, str]) -> str:
    """Approval (batch) dialog: frame, titles, fix items, badges, checkbox."""
    return f"""
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
"""


def _qss_confirm_dialog(c: dict[str, str]) -> str:
    """Confirm dialog: icon, title, description."""
    return f"""
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
"""


def _qss_splash(c: dict[str, str]) -> str:
    """Splash dialog: brand, tagline, badge, and per-step icon/label/result."""
    return f"""
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
