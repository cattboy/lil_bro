"""Stat tile shared by the dashboard's 4-col grid and the output view's LiveStatRow.

``StatCard`` is a label-over-value tile with a ``statTone`` chrome variant.
``STAT_CARDS`` is the canonical ``(key, label, tone)`` spec for the four core
system-stat tiles (CPU usage, CPU temp, GPU temp, RAM used) — the single
source of truth shared by ``Dashboard`` and ``LiveStatRow``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from src.gui.widgets.info_marker import InfoMarker


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

        # Header row: the small uppercase label, with room for an optional
        # "?" info marker mounted later via set_info() (temp tiles only).
        self._header = QHBoxLayout()
        self._header.setContentsMargins(0, 0, 0, 0)
        self._header.setSpacing(6)
        self._label = QLabel(label)
        self._label.setObjectName("cardLabel")
        self._header.addWidget(self._label)
        self._header.addStretch()
        layout.addLayout(self._header)
        self._info_marker: InfoMarker | None = None

        self._value = QLabel("—")
        self._value.setObjectName("cardValue")
        self._value.setProperty("statTone", tone)
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._value)

    def set_value(self, text: str) -> None:
        self._value.setText(text)

    def set_info(self, title: str, body: str) -> None:
        """Attach (or update) a hover "?" info marker on the header row.

        The marker shows ``title``/``body`` as a styled tooltip flyout on
        hover. The dashboard calls this for the CPU/GPU temperature tiles
        only; other tiles (and the LiveStatRow) never call it, so they stay
        marker-free.
        """
        if self._info_marker is None:
            self._info_marker = InfoMarker(title, body, parent=self)
            # Header order: index 0 = label, then marker, then the stretch.
            self._header.insertWidget(1, self._info_marker)
        else:
            self._info_marker.set_help(title, body)
