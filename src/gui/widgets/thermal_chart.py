"""Hand-rolled QPainter widget plotting CPU + GPU temperatures over time.

Chosen over QtCharts to avoid the +5 MB bundle dependency. Stores up
to 120 samples (2 minutes at 1 Hz) and rescales the y-axis so the
hottest reading sets the headroom. Color thresholds match DESIGN.md /
plan: warning at 75°C, critical at 85°C.
"""

from __future__ import annotations

from collections import deque

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QWidget


_MAX_SAMPLES = 120
_WARN_C = 75.0
_CRIT_C = 85.0


class ThermalChart(QWidget):
    """Live CPU + GPU temperature chart for the sidebar."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("thermalChart")
        self.setMinimumHeight(140)
        self.setAccessibleName("Thermal chart")
        self.setAccessibleDescription(
            "Live CPU and GPU temperatures. Yellow above 75°C, red above 85°C."
        )
        self._cpu_samples: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._gpu_samples: deque[float] = deque(maxlen=_MAX_SAMPLES)
        self._offline = True
        self._status_text = "Connecting…"

    # ── Public API ─────────────────────────────────────────────────────

    def append_sample(self, cpu_c: float | None, gpu_c: float | None) -> None:
        """Add one paired CPU/GPU sample. None values are skipped per series."""
        if cpu_c is not None:
            self._cpu_samples.append(float(cpu_c))
        if gpu_c is not None:
            self._gpu_samples.append(float(gpu_c))
        self._offline = False
        self._status_text = ""
        self.update()

    def set_offline(self, message: str = "Thermal monitor offline") -> None:
        """Render the offline overlay (used when LHM startup failed)."""
        self._offline = True
        self._status_text = message
        self.update()

    def clear_samples(self) -> None:
        self._cpu_samples.clear()
        self._gpu_samples.clear()
        self.update()

    @property
    def latest_cpu(self) -> float | None:
        return self._cpu_samples[-1] if self._cpu_samples else None

    @property
    def latest_gpu(self) -> float | None:
        return self._gpu_samples[-1] if self._gpu_samples else None

    # ── Painting ───────────────────────────────────────────────────────

    def paintEvent(self, _event):  # noqa: N802  Qt override
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._paint_background(painter)
            if self._offline or not (self._cpu_samples or self._gpu_samples):
                self._paint_status(painter)
                return
            ymax = max(_CRIT_C, max(self._cpu_samples or [0]), max(self._gpu_samples or [0])) + 5
            ymin = max(20.0, min(self._cpu_samples or [40], default=40), min(self._gpu_samples or [40], default=40)) - 5
            self._paint_thresholds(painter, ymin, ymax)
            self._paint_series(painter, self._cpu_samples, QColor("#00E5CC"), ymin, ymax)
            self._paint_series(painter, self._gpu_samples, QColor("#D183E8"), ymin, ymax)
            self._paint_legend(painter)
        finally:
            painter.end()

    def _paint_background(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor("#24252F"))
        painter.setPen(QPen(QColor("#363745"), 1))
        painter.drawRect(self.rect().adjusted(0, 0, -1, -1))

    def _paint_status(self, painter: QPainter) -> None:
        painter.setPen(QColor("#9B9AA0"))
        font = QFont("DM Sans", 10)
        painter.setFont(font)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._status_text)

    def _paint_thresholds(self, painter: QPainter, ymin: float, ymax: float) -> None:
        for c, color in ((_WARN_C, QColor("#FFB547")), (_CRIT_C, QColor("#FF6B6B"))):
            if not (ymin <= c <= ymax):
                continue
            y = self._y_for(c, ymin, ymax)
            pen = QPen(color, 1, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawLine(0, y, self.width(), y)

    def _paint_series(self, painter: QPainter, samples: deque[float],
                      color: QColor, ymin: float, ymax: float) -> None:
        if len(samples) < 2:
            return
        n = len(samples)
        step = self.width() / max(1, n - 1)
        points = [
            QPoint(int(i * step), self._y_for(v, ymin, ymax))
            for i, v in enumerate(samples)
        ]
        painter.setPen(QPen(color, 2))
        painter.drawPolyline(points)

    def _paint_legend(self, painter: QPainter) -> None:
        font = QFont("JetBrains Mono", 9)
        painter.setFont(font)
        legend = QRect(8, 8, 120, 18)
        painter.setPen(QColor("#00E5CC"))
        painter.drawText(legend, Qt.AlignmentFlag.AlignLeft, "CPU")
        legend.translate(0, 16)
        painter.setPen(QColor("#D183E8"))
        painter.drawText(legend, Qt.AlignmentFlag.AlignLeft, "GPU")

    def _y_for(self, value: float, ymin: float, ymax: float) -> int:
        h = self.height()
        span = max(1.0, ymax - ymin)
        normalized = (value - ymin) / span
        return int(h - (normalized * (h - 8)) - 4)
