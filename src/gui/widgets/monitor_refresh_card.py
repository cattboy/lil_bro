"""Dashboard card showing per-monitor current vs max refresh rate.

When any monitor is running below its supported maximum, a "Fix Now"
button is exposed that emits ``fix_requested``. The signal is bubbled
up through Dashboard → app.py, which shows a BatchSelectionDialog and
spawns a worker thread that runs ``execute_fix("display", specs)``.
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
class MonitorRefreshCard(QFrame):
    """Always-visible per-monitor card. Emits ``fix_requested(device)``."""

    fix_requested = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorCard")
        self.setAccessibleName("Monitor refresh rate card")

        self._device: str = ""

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Left column: device + value + status
        left = QVBoxLayout()
        left.setSpacing(4)

        self._device_lbl = QLabel("—")
        self._device_lbl.setObjectName("pollLabel")
        left.addWidget(self._device_lbl)

        hz_row = QHBoxLayout()
        hz_row.setSpacing(4)
        self._val_lbl = QLabel("—")
        self._val_lbl.setObjectName("pollValue")
        self._unit_lbl = QLabel("Hz")
        self._unit_lbl.setObjectName("pollUnit")
        hz_row.addWidget(self._val_lbl)
        hz_row.addWidget(self._unit_lbl)
        hz_row.addStretch()
        left.addLayout(hz_row)

        # Severity tinting (sev = low/medium/high) is applied in set_display
        # based on optimal/suboptimal/WMI state. Theme rules live in
        # src/gui/theme.py (QLabel#pollStatus[sev=…], QLabel#pollValue[sev=…]).
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("pollStatus")
        left.addWidget(self._status_lbl)

        root.addLayout(left)
        root.addStretch()

        # Right: Fix button (hidden when optimal)
        self._fix_btn = QPushButton("Fix Now")
        self._fix_btn.setObjectName("primary")
        self._fix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._fix_btn.setFixedWidth(120)
        self._fix_btn.setVisible(False)
        self._fix_btn.clicked.connect(self._on_fix_clicked)
        root.addWidget(self._fix_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_display(self, d: dict) -> None:
        """Populate the card from one ``DisplayCapabilities`` entry."""
        from src.llm.action_proposer import propose_for_check
        raw_device = str(d.get("device") or "Display")
        is_wmi = (d.get("source") == "wmi") or raw_device.startswith("WMI:")
        display_name = raw_device[4:] if raw_device.startswith("WMI:") else raw_device
        self._device = raw_device

        cur = int(d.get("current_refresh_hz") or 0)
        mx = int(d.get("max_refresh_hz") or 0)
        at_res = str(d.get("at_resolution") or "")

        self._device_lbl.setText(display_name)
        self._val_lbl.setText(str(cur) if cur else "—")

        if is_wmi:
            # WMI fallback: refresh detection is limited; no Fix button (legacy
            # _fix_display can't target a synthesized WMI: device name).
            # Diagnostic copy, not a proposal — kept inline (no FALLBACK entry).
            self._status_lbl.setText("Detected via WMI — refresh rate detection limited")
            self._status_lbl.setToolTip("")
            self._status_lbl.setProperty("sev", "medium")
            self._val_lbl.setProperty("sev", "medium")
            self._fix_btn.setVisible(False)
        else:
            optimal = cur > 0 and mx > 0 and cur >= mx
            if optimal:
                # Pass state, not a proposal — no FALLBACK entry by design.
                self._status_lbl.setText(f"✓ Running at max refresh rate ({mx} Hz)")
                self._status_lbl.setToolTip("")
                self._status_lbl.setProperty("sev", "low")
                self._val_lbl.setProperty("sev", "low")
                self._fix_btn.setVisible(False)
            else:
                # FAIL tier — canonical text from FALLBACK_PROPOSALS["display"],
                # full explanation on hover. Single source of truth shared with
                # pipeline approval flow.
                proposal = propose_for_check(
                    "display",
                    {"current": cur, "expected": mx, "at_resolution": at_res},
                )
                self._status_lbl.setText(proposal["proposed_action"])
                self._status_lbl.setToolTip(proposal["explanation"])
                self._status_lbl.setProperty("sev", "medium")
                self._val_lbl.setProperty("sev", "medium")
                self._fix_btn.setVisible(True)

        # Re-polish unconditionally for both labels — QSS attribute selectors
        # only re-evaluate when style is repolished. Done at the bottom so
        # whichever branch ran above gets its sev write picked up.
        repolish(self._status_lbl)
        repolish(self._val_lbl)
    def _on_fix_clicked(self) -> None:
        if self._device:
            self.fix_requested.emit(self._device)



class MonitorEmptyCard(QFrame):
    """Fallback card shown when ``DisplayCapabilities`` is empty.

    Keeps the Monitor Refresh feature visible (and recoverable) even
    when both the strict EnumDisplayDevicesW path and the WMI fallback
    returned nothing.
    """

    refresh_requested = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("monitorEmptyCard")
        self.setAccessibleName("Monitor refresh rate — no displays detected")

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        title = QLabel("⚠  No displays detected")
        title.setObjectName("pollLabel")
        # sev=high turns the title coral via the pollLabel[sev="high"] QSS
        # rule in theme.py. Init-time set, no re-polish needed before first paint.
        title.setProperty("sev", "high")
        left.addWidget(title)

        hint = QLabel("Click Refresh to re-query Windows.")
        hint.setObjectName("pollStatus")
        # Intentionally no sev — hint stays in default secondary-text color.
        left.addWidget(hint)

        root.addLayout(left)
        root.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("secondary")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.setFixedWidth(120)
        self._refresh_btn.clicked.connect(self.refresh_requested.emit)
        root.addWidget(self._refresh_btn, alignment=Qt.AlignmentFlag.AlignVCenter)
