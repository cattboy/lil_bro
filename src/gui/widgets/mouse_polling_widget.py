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

        self._hz_label = QLabel("---")
        self._hz_label.setObjectName("cardValue")
        self._hz_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hz_label)

        unit = QLabel("Hz")
        unit.setObjectName("cardLabel")
        unit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(unit)

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

    # ── Sampling control ───────────────────────────────────────────────

    def start_sampling(self) -> None:
        self._sample_count = 0
        self._sample_started_at = None
        self._last_pos = (None, None)
        self._best_hz = 0
        self._hz_label.setText("---")
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
        super().mouseMoveEvent(event)

    # ── Completion ─────────────────────────────────────────────────────

    def _finish(self) -> None:
        self._auto_stop_timer.stop()
        if self._sample_count == 0:
            self._hz_label.setText("no input detected")
            return
        self.measurement_complete.emit(self._best_hz)

    @property
    def measured_hz(self) -> int:
        return self._best_hz

    @property
    def sample_count(self) -> int:
        return self._sample_count
