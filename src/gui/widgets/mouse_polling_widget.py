"""Custom QWidget that replaces the CLI ``Press Enter when ready`` mouse test.

Instead of asking the user to press Enter and then sampling
``GetCursorPos`` for 5 seconds, the GUI gives them a target area to
move the mouse over and reads ``mouseMoveEvent`` deliveries directly.
Live Hz read-out updates as samples arrive; a Done button ends the
sample early; a 5-second QTimer auto-stops if the user is patient.

Hz formula matches the CLI fallback in ``src/agent_tools/mouse.py``:
``samples / duration``. (Qt's event delivery rate is constrained by
the same OS-level cursor position cadence GetCursorPos polls.)
"""

from __future__ import annotations

import time

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


_SAMPLE_WINDOW_SEC = 5.0


class MousePollingWidget(QWidget):
    """Live-Hz mouse polling test."""

    measurement_complete = Signal(int)  # measured_hz

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("mousePollingWidget")
        self.setAccessibleName("Mouse polling test")
        self.setMouseTracking(True)
        self.setMinimumSize(480, 280)

        self._sample_count = 0
        self._sample_started_at: float | None = None
        self._last_pos = (None, None)
        self._best_hz = 0
        self._auto_stop_timer = QTimer(self)
        self._auto_stop_timer.setSingleShot(True)
        self._auto_stop_timer.timeout.connect(self._finish)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 32, 48, 32)
        layout.setSpacing(16)

        title = QLabel("Move your mouse here")
        title.setObjectName("sectionHeader")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # objectName="pollValue" picks up the 36px monospace styling from
        # theme.py (vs cardValue's 24px) — matches this widget's primary-number
        # role. Severity tinting (sev=low/medium/high) is applied live in
        # mouseMoveEvent based on tier; pollValue[sev=…] QSS rules color it.
        self._hz_label = QLabel("---")
        self._hz_label.setObjectName("pollValue")
        self._hz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hz_label)

        unit = QLabel("Hz")
        unit.setObjectName("cardLabel")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(unit)

        # Tier text: "Low" / "Medium" / "High" / "No input". Colored via
        # pollStatus[sev=…] QSS to match the Hz number above. Naming maps
        # tier → Hz quality (Low Hz = poor → coral; High Hz = excellent →
        # mint). Underlying sev property uses fixSev semantics
        # (high severity = coral); the text-vs-sev inversion is intentional
        # so the visible word matches user intuition for performance tiers.
        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("pollStatus")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status_lbl)

        layout.addStretch(1)

        actions = QHBoxLayout()
        actions.addStretch(1)
        self.retry_btn = QPushButton("Retry")
        self.done_btn = QPushButton("Done")
        self.done_btn.setObjectName("primary")
        actions.addWidget(self.retry_btn)
        actions.addWidget(self.done_btn)
        layout.addLayout(actions)

        self.retry_btn.clicked.connect(self.start_sampling)
        self.done_btn.clicked.connect(self._finish)

        self.start_sampling()

    def _set_hz_sev(self, sev: str) -> None:
        """Set severity tone on the Hz label and re-polish so QSS applies."""
        self._hz_label.setProperty("sev", sev)
        self._hz_label.style().unpolish(self._hz_label)
        self._hz_label.style().polish(self._hz_label)

    def _set_tier(self, sev: str, label: str) -> None:
        """Set Hz-label tint AND status-label text+tint together.

        sev: "low" | "medium" | "high" | "" (neutral)
            — controls color via QSS pollValue[sev]/pollStatus[sev]
        label: human-readable tier text shown under "Hz"
            — "Low" / "Medium" / "High" / "No input" / "" (cleared)
        """
        self._set_hz_sev(sev)
        self._status_lbl.setText(label)
        self._status_lbl.setProperty("sev", sev)
        self._status_lbl.style().unpolish(self._status_lbl)
        self._status_lbl.style().polish(self._status_lbl)

    def _set_hz_sev(self, sev: str) -> None:
        """Set severity tone on the Hz label and re-polish so QSS applies."""
        self._hz_label.setProperty("sev", sev)
        self._hz_label.style().unpolish(self._hz_label)
        self._hz_label.style().polish(self._hz_label)

    # ── Sampling control ───────────────────────────────────────────────

    def start_sampling(self) -> None:
        self._sample_count = 0
        self._sample_started_at = None
        self._last_pos = (None, None)
        self._best_hz = 0
        self._hz_label.setText("---")
        # Clear tier + neutral white tint between sample windows.
        self._set_tier("", "")
        self._auto_stop_timer.start(int(_SAMPLE_WINDOW_SEC * 1000))

    # ── Mouse capture ──────────────────────────────────────────────────

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        pos = (event.position().x(), event.position().y())
        if pos == self._last_pos:
            return
        self._last_pos = pos

        if self._sample_started_at is None:
            self._sample_started_at = time.monotonic()
        self._sample_count += 1

        elapsed = time.monotonic() - self._sample_started_at
        if elapsed > 0:
            current_hz = round(self._sample_count / elapsed)
            self._best_hz = max(self._best_hz, current_hz)
            self._hz_label.setText(str(current_hz))
            # Tier the Hz label + status text. Text labels match Hz tier
            # ("Low" = low Hz = poor); underlying sev matches fixSev
            # severity (high sev = coral) so QSS colors align.
            if current_hz >= 1000:
                self._set_tier("low", "High")
            elif current_hz >= 500:
                self._set_tier("medium", "Medium")
            else:
                self._set_tier("high", "Low")
        super().mouseMoveEvent(event)

    # ── Completion ─────────────────────────────────────────────────────

    def _finish(self) -> None:
        self._auto_stop_timer.stop()
        if self._sample_count == 0:
            self._hz_label.setText("no input detected")
            # Coral — no input is a problem state.
            self._set_tier("high", "No input")
            return
        self.measurement_complete.emit(self._best_hz)

    @property
    def measured_hz(self) -> int:
        return self._best_hz

    @property
    def sample_count(self) -> int:
        return self._sample_count
