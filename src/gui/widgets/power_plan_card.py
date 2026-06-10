"""Dashboard card for the Windows power-plan one-click fix.

À-la-carte counterpart to the pipeline's power_plan fix (the pipeline is the
"apply all fixes" path; dashboard cards let users pick and choose). Shown when
the ``PowerPlan`` spec entry was collected; the Fix Now button appears when
the active plan is not a performance plan. The button emits
``apply_requested``, bubbled through Dashboard →
``StartupCoordinator.on_power_plan_fix_requested``, which gates approval with
a BatchSelectionDialog (+ restore-point prompt) and spawns a worker that runs
``execute_fix("power_plan", specs)``.

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

from src.gui.theme import repolish
from src.llm.action_proposer import propose_for_check

# Optimistic post-fix text for a bare {"status": "OK"} finding (no message).
_APPLIED_TEXT = "✓ High-performance plan active"


class PowerPlanCard(QFrame):
    """Power-plan fix card. Emits ``apply_requested`` on Fix Now."""

    apply_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorCard")
        self.setAccessibleName("Power Plan card")

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        self._title_lbl = QLabel("Power Plan")
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
        """Render an ``analyze_power_plan`` finding dict onto the card.

        A bare ``{"status": "OK"}`` (no message) is the optimistic post-fix
        state (mirrors ``set_nvidia_profile_findings``).
        """
        message = str(result.get("message") or "")
        if result.get("status") == "OK":
            # Pass/applied state, not a proposal — no FALLBACK entry by design.
            self._status_lbl.setText(f"✓ {message}" if message else _APPLIED_TEXT)
            self._status_lbl.setToolTip("")
            self._status_lbl.setProperty("sev", "low")
            self._apply_btn.setVisible(False)
        else:
            # WARNING tier — analyzer message states the current plan; the
            # canonical explanation from FALLBACK_PROPOSALS["power_plan"]
            # (severity HIGH → sev "high") rides the tooltip. Single source
            # of truth shared with the pipeline approval flow.
            prop = propose_for_check("power_plan") or {}
            self._status_lbl.setText(message or str(prop.get("proposed_action", "")))
            self._status_lbl.setToolTip(str(prop.get("explanation", "")))
            self._status_lbl.setProperty("sev", "high")
            self._apply_btn.setVisible(True)
        repolish(self._status_lbl)

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit()
