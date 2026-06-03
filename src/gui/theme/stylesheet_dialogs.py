"""Dialog QSS: approval dialog, confirm dialog, mouse-ready dialog, splash, output header."""

from __future__ import annotations

from src.gui.theme.tokens import FONTS


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
    QLabel#fixNum {{
        font-family: "{FONTS["mono"]}";
        font-size: 12px;
        font-weight: 600;
        color: {c["text_muted"]};
        min-width: 20px;
        min-height: 20px;
        border: 1px solid {c["border_default"]};
        border-radius: 4px;
        padding: 1px 4px;
    }}
"""


def _qss_confirm_dialog(c: dict[str, str]) -> str:
    """Confirm dialog: elevated card, icon, title, description, prominent W button."""
    return f"""
    /* --- Confirm dialog visual update -------------------------------- */
    QDialog#confirmDialog {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 12px;
    }}
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
    /* Make the W/accept button the clear focal point: accent fill (from the
       global #primary rule) plus extra weight and breathing room so it reads
       as the primary action against the secondary (S) button. */
    QDialog#confirmDialog QPushButton#primary {{
        padding: 10px 22px;
        font-size: 14px;
        font-weight: 700;
        min-height: 18px;
    }}
"""


def _qss_mouse_ready_dialog(c: dict[str, str]) -> str:
    """Mouse polling ready dialog: accent bar, title, description."""
    return f"""
    /* --- Mouse ready dialog ------------------------------------------ */
    QFrame#mouseReadyAccent {{
        background-color: {c["accent"]};
        border-radius: 1px;
        min-height: 2px;
        max-height: 2px;
    }}
    QLabel#mouseReadyTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 14px;
        font-weight: 700;
        color: {c["text_primary"]};
    }}
    QLabel#mouseReadyDesc {{
        font-size: 12px;
        color: {c["text_secondary"]};
        line-height: 1.5;
    }}
"""


def _qss_admin_dialog(c: dict[str, str]) -> str:
    """Admin (not-elevated) warning dialog: warning icon, title, description, OK button."""
    return f"""
    /* --- Admin warning dialog ---------------------------------------- */
    QDialog#adminDialog {{
        background-color: {c["surface"]};
        border: 1px solid {c["border_default"]};
        border-radius: 12px;
    }}
    QLabel#adminIcon {{
        font-size: 28px;
        color: {c["warning"]};
    }}
    QLabel#adminTitle {{
        font-family: "{FONTS["mono"]}";
        font-size: 14px;
        font-weight: 600;
        color: {c["text_primary"]};
    }}
    QLabel#adminDesc {{
        font-size: 12px;
        color: {c["text_muted"]};
        line-height: 1.5;
    }}
    QDialog#adminDialog QPushButton#primary {{
        padding: 10px 22px;
        font-size: 14px;
        font-weight: 700;
        min-height: 18px;
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
