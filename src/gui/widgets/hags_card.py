"""Dashboard card for the Hardware-Accelerated GPU Scheduling (HAGS) one-click fix.

À-la-carte counterpart to the pipeline's hags fix (the pipeline is the
"apply all fixes" path; dashboard cards let users pick and choose). Shown when
the ``HAGS`` spec entry was collected AND the feature is supported; the Fix Now
button appears when HAGS is disabled. The button emits ``apply_requested``,
bubbled through Dashboard → ``StartupCoordinator.on_hags_fix_requested``, which
gates approval with a BatchSelectionDialog (+ restore-point prompt) and spawns a
worker that runs ``execute_fix("hags", specs)``.

HAGS only takes effect after a reboot, so the post-fix text says so.

Reuses MonitorRefreshCard's QSS objectNames (``monitorCard``, ``pollLabel``,
``pollStatus``, ``primary``) so no new theme rules are required.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from src.gui.theme import repolish, set_apply_busy
from src.llm.action_proposer import propose_for_check

# Optimistic post-fix text for a bare {"status": "OK"} finding (no message).
# HAGS needs a reboot to take effect, so the copy says so.
_APPLIED_TEXT = "✓ HAGS enabled — restart to apply"


class HAGSCard(QFrame):
    """HAGS fix card. Emits ``apply_requested`` on Fix Now."""

    apply_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorCard")
        self.setAccessibleName("Hardware-Accelerated GPU Scheduling card")

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        self._title_lbl = QLabel("Hardware-Accelerated GPU Scheduling")
        self._title_lbl.setObjectName("pollLabel")
        left.addWidget(self._title_lbl)

        self._status_lbl = QLabel("—")
        self._status_lbl.setObjectName("pollStatus")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setProperty("sev", "medium")
        left.addWidget(self._status_lbl)

        root.addLayout(left, 1)

        self._apply_btn = QPushButton("Fix Now")
        self._apply_btn.setObjectName("primary")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setFixedWidth(140)
        self._apply_btn.setVisible(False)
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        root.addWidget(self._apply_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_findings(self, result: dict) -> None:
        """Render an ``analyze_hags`` finding dict onto the card.

        Only WARNING (HAGS off + supported) shows the Fix Now button. A bare
        ``{"status": "OK"}`` (no message) is the optimistic post-fix state
        (mirrors the Game Mode card). SKIPPED (unsupported) shows the plain
        message with no button -- though the card is normally hidden then.
        """
        message = str(result.get("message") or "")
        status = result.get("status")
        if status == "WARNING":
            # WARNING tier -- analyzer message states the current state; the
            # canonical explanation from FALLBACK_PROPOSALS["hags"] (severity
            # MEDIUM → sev "medium") rides the tooltip. Single source of truth
            # shared with the pipeline approval flow.
            prop = propose_for_check("hags") or {}
            self._status_lbl.setText(message or str(prop.get("proposed_action", "")))
            self._status_lbl.setToolTip(str(prop.get("explanation", "")))
            self._status_lbl.setProperty("sev", "medium")
            self._apply_btn.setVisible(True)
        elif status == "OK":
            # Pass/applied state, not a proposal -- no FALLBACK entry by design.
            self._status_lbl.setText(f"✓ {message}" if message else _APPLIED_TEXT)
            self._status_lbl.setToolTip("")
            self._status_lbl.setProperty("sev", "low")
            self._apply_btn.setVisible(False)
        else:
            # SKIPPED / unknown: neutral text, no action (card usually hidden).
            self._status_lbl.setText(message)
            self._status_lbl.setToolTip("")
            self._status_lbl.setProperty("sev", "low")
            self._apply_btn.setVisible(False)
        repolish(self._status_lbl)

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit()

    def set_applying(self, applying: bool) -> None:
        """Reflect an in-flight fix on the Fix Now button (busy <-> idle)."""
        set_apply_busy(self._apply_btn, applying)
