"""Per-phase status card with a header label and a QProgressBar.

Status transitions: ``pending`` → ``active`` → ``done`` (or ``failed``).
QSS styling lives in ``theme.py`` and switches on the
``phaseStatus`` dynamic property.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
)


class PhaseCard(QFrame):
    """A single phase card — used in the horizontal phase row on the output view."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    _STATUS_TEXT = {
        STATUS_PENDING: "○ PENDING",
        STATUS_ACTIVE:  "● RUNNING",
        STATUS_DONE:    "✓ COMPLETE",
        STATUS_FAILED:  "✕ FAILED",
    }

    def __init__(self, num: int, name: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("phaseCard")
        self.setProperty("phaseStatus", self.STATUS_PENDING)
        self.setSizePolicy(
            self.sizePolicy().horizontalPolicy(),
            self.sizePolicy().verticalPolicy(),
        )
        self.setAccessibleName(f"Phase {num}: {name}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(3)

        self._num_label = QLabel(f"PHASE {num:02d}")
        self._num_label.setObjectName("phaseNum")

        self._name_label = QLabel(name)
        self._name_label.setObjectName("phaseName")

        self._status_label = QLabel(self._STATUS_TEXT[self.STATUS_PENDING])
        self._status_label.setObjectName("phaseStatus")
        self._status_label.setProperty("phaseStatus", self.STATUS_PENDING)

        layout.addWidget(self._num_label)
        layout.addWidget(self._name_label)
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(3)
        self._progress.setVisible(False)
        self._progress.setAccessibleName(f"{name} progress")
        layout.addWidget(self._progress)

    # ── State transitions ──────────────────────────────────────────────

    def set_status(self, status: str) -> None:
        if status not in (self.STATUS_PENDING, self.STATUS_ACTIVE,
                          self.STATUS_DONE, self.STATUS_FAILED):
            raise ValueError(f"unknown phase status: {status}")
        self.setProperty("phaseStatus", status)
        self._status_label.setText(self._STATUS_TEXT[status])
        self._status_label.setProperty("phaseStatus", status)

        self._progress.setVisible(status == self.STATUS_ACTIVE)
        if status == self.STATUS_DONE:
            self._progress.setValue(100)
        elif status == self.STATUS_PENDING:
            self._progress.setValue(0)

        for widget in (self, self._status_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    @property
    def status(self) -> str:
        return self.property("phaseStatus") or self.STATUS_PENDING

    # ── Progress signal slot ───────────────────────────────────────────

    def update_progress(self, percent: int, label: str = "") -> None:
        """Slot wired to the ``progress_changed(percent, label)`` signal."""
        self._progress.setValue(max(0, min(100, percent)))
