"""Dashboard card for NVIDIA driver-profile one-click fixes.

Shown on the Dashboard when nvidia-smi detects an NVIDIA GPU with NPI
available. The Apply button emits ``apply_requested(check_name)``, bubbled up
through Dashboard → StartupCoordinator, which gates approval with a
BatchSelectionDialog (+ restore-point prompt) and spawns a worker that runs
``execute_fix(check_name, specs)``.

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


class NvidiaProfileCard(QFrame):
    """NVCP profile card. Emits ``apply_requested(check_name)``."""

    apply_requested = Signal(str)

    def __init__(
        self,
        check_name: str,
        title: str,
        button_label: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("monitorCard")
        self.setAccessibleName(f"{title} card")

        self._check_name = check_name

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("pollLabel")
        left.addWidget(self._title_lbl)

        self._status_lbl = QLabel("—")
        self._status_lbl.setObjectName("pollStatus")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setProperty("sev", "medium")
        left.addWidget(self._status_lbl)

        root.addLayout(left)
        root.addStretch()

        self._apply_btn = QPushButton(button_label)
        self._apply_btn.setObjectName("primary")
        self._apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_btn.setFixedWidth(140)
        self._apply_btn.clicked.connect(self._on_apply_clicked)
        root.addWidget(self._apply_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_gpu(self, gpu_name: str, status_text: str, tooltip: str = "") -> None:
        """Populate the card with the detected GPU and the recommended action."""
        self._status_lbl.setText(f"{gpu_name} — {status_text}" if gpu_name else status_text)
        self._status_lbl.setToolTip(tooltip)
        repolish(self._status_lbl)

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit(self._check_name)
