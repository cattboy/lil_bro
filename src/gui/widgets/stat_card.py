"""Stat tile shared by the dashboard's 4-col grid and the output view's LiveStatRow.

``StatCard`` is a label-over-value tile with a ``statTone`` chrome variant.
``STAT_CARDS`` is the canonical ``(key, label, tone)`` spec for the four core
system-stat tiles (CPU usage, CPU temp, GPU temp, RAM used) — the single
source of truth shared by ``Dashboard`` and ``LiveStatRow``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


STAT_CARDS = (
    ("cpu_usage", "CPU USAGE", "norm"),
    ("cpu_temp",  "CPU TEMP",  "warn"),
    ("gpu_temp",  "GPU TEMP",  "ok"),
    ("ram_used",  "RAM USED",  "cyan"),
)


class StatCard(QFrame):
    """One tile in the 4-col stat grid. Supports tone variants."""

    def __init__(self, label: str, tone: str = "norm", parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        self.setProperty("statTone", tone)
        self.setAccessibleName(f"Dashboard card: {label}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(4)

        self._label = QLabel(label)
        self._label.setObjectName("cardLabel")
        layout.addWidget(self._label)

        self._value = QLabel("—")
        self._value.setObjectName("cardValue")
        self._value.setProperty("statTone", tone)
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)
