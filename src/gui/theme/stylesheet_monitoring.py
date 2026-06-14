"""Monitoring QSS: stat cards, thermal chart, poll widgets, phase row."""

from __future__ import annotations

from src.gui.theme.tokens import FONTS


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
    QFrame#monitorEmptyCard,
    QFrame#lastRunCard {{
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


def _qss_dashboard_scroll(c: dict[str, str]) -> str:
    """Dashboard scroll viewport + pulsing scroll-hint chip."""
    return f"""
    /* --- Dashboard scroll area --------------------------------------- */
    /* Transparent shell so the deep window background shows through; the
     * scrollbar itself is themed by the global QScrollBar rules. */
    QScrollArea#dashboardScroll {{
        background-color: transparent;
        border: none;
    }}
    QScrollArea#dashboardScroll > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* Scroll-hint chip — circular, amber ring on elevated surface. The glow
     * pulse is a QGraphicsDropShadowEffect animation (ScrollHintArrow),
     * not QSS — Qt QSS has no box-shadow. */
    QToolButton#scrollHintArrow {{
        background-color: {c["elevated"]};
        color: {c["warning"]};
        border: 1px solid {c["warning"]};
        border-radius: 16px;  /* half the 32px chip — fully round */
        font-size: 13px;
    }}
    QToolButton#scrollHintArrow:hover {{
        background-color: {c["hover"]};
        border: 1px solid {c["warning"]};
    }}
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
