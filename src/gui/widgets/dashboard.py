"""6-card glance dashboard for the home view.

Cards: power plan, Game Mode, primary refresh rate, mouse Hz, CPU
temp, GPU temp. Polls ``quick_status_snapshot`` every 5 seconds via a
QTimer in a dedicated worker QThread (separate from the pipeline
worker so polling cadence isn't coupled to pipeline lifecycle).

Polling pauses between ``pipeline_started`` and ``pipeline_finished``
signals so the home view doesn't compete with the pipeline for
registry / WMI access while a fix is mid-flight.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.agent_tools.quick_status import quick_status_snapshot


_POLL_INTERVAL_MS = 5000
_CARDS = (
    ("power_plan",   "POWER PLAN"),
    ("game_mode",    "GAME MODE"),
    ("refresh_rate", "REFRESH"),
    ("mouse_hz",     "MOUSE Hz"),
    ("cpu_temp",     "CPU TEMP"),
    ("gpu_temp",     "GPU TEMP"),
)


class DashboardWorker(QObject):
    """Polls quick_status_snapshot at 5-sec cadence on its own QThread."""

    snapshot_ready = Signal(dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer: QTimer | None = None
        self._lhm = None
        self._paused = False

    def set_lhm(self, lhm) -> None:
        self._lhm = lhm

    def start(self) -> None:
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._tick)
            self._timer.start(_POLL_INTERVAL_MS)
        self._tick()  # immediate first sample

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()
            self._timer = None

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False
        self._tick()

    def _tick(self) -> None:
        if self._paused:
            return
        try:
            self.snapshot_ready.emit(quick_status_snapshot(self._lhm))
        except Exception:
            self.snapshot_ready.emit({})


class _DashboardCard(QFrame):
    """One tile in the 2×3 grid."""

    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardCard")
        self.setAccessibleName(f"Dashboard card: {label}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        self._label = QLabel(label)
        self._label.setObjectName("cardLabel")
        layout.addWidget(self._label)

        self._value = QLabel("…")
        self._value.setObjectName("cardValue")
        self._value.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._value)
        layout.addStretch(1)

    def set_value(self, text: str) -> None:
        self._value.setText(text)


class Dashboard(QWidget):
    """Home view containing the 6-card glance grid + Run button (above grid)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Dashboard view")

        layout = QGridLayout(self)
        layout.setContentsMargins(48, 16, 48, 48)
        layout.setHorizontalSpacing(48)
        layout.setVerticalSpacing(24)

        self._cards: dict[str, _DashboardCard] = {}
        for idx, (key, label) in enumerate(_CARDS):
            card = _DashboardCard(label)
            self._cards[key] = card
            row, col = divmod(idx, 3)
            layout.addWidget(card, row, col)

        self._worker_thread: QThread | None = None
        self._worker: DashboardWorker | None = None

    # ── Polling lifecycle ──────────────────────────────────────────────

    def start_polling(self, lhm=None) -> None:
        if self._worker is not None:
            return
        self._worker_thread = QThread(self)
        self._worker = DashboardWorker()
        self._worker.set_lhm(lhm)
        self._worker.moveToThread(self._worker_thread)
        self._worker.snapshot_ready.connect(self.apply_snapshot)
        self._worker_thread.started.connect(self._worker.start)
        self._worker_thread.start()

    def stop_polling(self) -> None:
        if self._worker is None or self._worker_thread is None:
            return
        self._worker.stop()
        self._worker_thread.quit()
        self._worker_thread.wait(1000)
        self._worker = None
        self._worker_thread = None

    def pause_polling(self) -> None:
        if self._worker is not None:
            self._worker.pause()

    def resume_polling(self) -> None:
        if self._worker is not None:
            self._worker.resume()

    # ── Render slot ────────────────────────────────────────────────────

    def apply_snapshot(self, snapshot: dict) -> None:
        for key, card in self._cards.items():
            card.set_value(str(snapshot.get(key, "—")))
