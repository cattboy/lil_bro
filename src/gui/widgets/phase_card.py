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
    """A single phase row in the sidebar."""

    STATUS_PENDING = "pending"
    STATUS_ACTIVE = "active"
    STATUS_DONE = "done"
    STATUS_FAILED = "failed"

    def __init__(self, name: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("phaseCard")
        self.setProperty("phaseStatus", self.STATUS_PENDING)
        self.setAccessibleName(f"Phase: {name}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        header.setSpacing(8)
        self._name_label = QLabel(name)
        self._name_label.setObjectName("cardLabel")
        header.addWidget(self._name_label, stretch=1)
        self._status_label = QLabel("pending")
        self._status_label.setObjectName("cardLabel")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        header.addWidget(self._status_label)
        layout.addLayout(header)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        self._progress.setAccessibleName(f"{name} progress")
        layout.addWidget(self._progress)

    # ── State transitions ──────────────────────────────────────────────

    def set_status(self, status: str) -> None:
        if status not in (self.STATUS_PENDING, self.STATUS_ACTIVE,
                          self.STATUS_DONE, self.STATUS_FAILED):
            raise ValueError(f"unknown phase status: {status}")
        self.setProperty("phaseStatus", status)
        self._status_label.setText(status)
        # Force QSS re-evaluation so the status colors actually swap.
        self.style().unpolish(self)
        self.style().polish(self)

        if status == self.STATUS_DONE:
            self._progress.setValue(100)
        elif status == self.STATUS_PENDING:
            self._progress.setValue(0)

    @property
    def status(self) -> str:
        return self.property("phaseStatus") or self.STATUS_PENDING

    # ── Progress signal slot ───────────────────────────────────────────

    def update_progress(self, percent: int, label: str = "") -> None:
        """Slot wired to the ``progress_changed(percent, label)`` signal."""
        self._progress.setValue(max(0, min(100, percent)))
        if label:
            self._status_label.setText(label)
