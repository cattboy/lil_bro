"""Dashboard card for NVIDIA driver-profile one-click fixes.

Reusable card shown on the Dashboard when nvidia-smi detects an NVIDIA GPU.
Instantiated twice: once for the DLSS-only preset fix, once for the full
profile optimization. The Apply button emits ``apply_requested(check_name)``,
bubbled up through Dashboard → StartupCoordinator, which gates approval with a
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
    """NVIDIA fix card. Emits ``apply_requested(check_name)``.

    The DLSS variant (``with_priority_toggle=True``) also shows a Quality/FPS
    segmented toggle and emits ``priority_changed("quality"|"fps")`` when the
    user flips it. The toggle makes no system change on its own -- only Apply does.
    """

    apply_requested = Signal(str)
    priority_changed = Signal(str)

    def __init__(
        self,
        check_name: str,
        title: str,
        button_label: str,
        parent=None,
        *,
        with_priority_toggle: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("monitorCard")
        self.setAccessibleName(f"{title} card")

        self._check_name = check_name

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # Left column: title + GPU/recommendation status (+ optional toggle).
        left = QVBoxLayout()
        left.setSpacing(4)

        self._title_lbl = QLabel(title)
        self._title_lbl.setObjectName("pollLabel")
        left.addWidget(self._title_lbl)

        # Severity tinting (sev=medium) reuses the theme rules shared with the
        # monitor card; the status text (GPU + recommendation) is set in set_gpu.
        self._status_lbl = QLabel("—")
        self._status_lbl.setObjectName("pollStatus")
        self._status_lbl.setWordWrap(True)
        self._status_lbl.setProperty("sev", "medium")
        left.addWidget(self._status_lbl)

        # Optional quality/FPS toggle (DLSS card only). Two checkable, mutually
        # exclusive QPushButtons (gui-widget-over-dropdown). autoDefault False so
        # the WASD/Enter input layer never lands on them.
        self._quality_btn: QPushButton | None = None
        self._fps_btn: QPushButton | None = None
        if with_priority_toggle:
            toggle_row = QHBoxLayout()
            toggle_row.setSpacing(6)
            self._quality_btn = QPushButton("Quality")
            self._fps_btn = QPushButton("FPS")
            for btn, value in ((self._quality_btn, "quality"), (self._fps_btn, "fps")):
                btn.setObjectName("secondary")
                btn.setCheckable(True)
                btn.setAutoExclusive(True)
                btn.setAutoDefault(False)
                btn.setDefault(False)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.setFixedHeight(26)
                btn.clicked.connect(lambda _checked=False, v=value: self._on_priority_clicked(v))
                toggle_row.addWidget(btn)
            toggle_row.addStretch()
            self._quality_btn.setChecked(True)
            left.addLayout(toggle_row)

        root.addLayout(left)
        root.addStretch()

        # Right: Apply button (the card itself is shown/hidden by the Dashboard;
        # the button stays visible whenever the card is shown).
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

    def set_priority(self, priority: str) -> None:
        """Reflect the current priority on the toggle (no signal emitted)."""
        if self._quality_btn is None or self._fps_btn is None:
            return
        self._quality_btn.setChecked(priority == "quality")
        self._fps_btn.setChecked(priority == "fps")

    def _on_priority_clicked(self, priority: str) -> None:
        self.priority_changed.emit(priority)

    def _on_apply_clicked(self) -> None:
        self.apply_requested.emit(self._check_name)
