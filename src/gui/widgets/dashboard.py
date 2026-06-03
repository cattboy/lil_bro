"""Glance dashboard for the home view.

Stat cards (CPU usage, CPU temp, GPU temp, RAM used), a temperature
chart and a USB-polling widget. ``SystemStatsWorker`` (in ``src/gui/worker.py``)
polls system stats every 5 seconds on a dedicated QThread and feeds both this
view and the optimization view's ``LiveStatRow`` (via the ``stats_ready``
signal), so both always display identical values.

The worker uses only the pipeline-safe data subset (psutil + a single
LHM read), so polling runs continuously -- it is not paused during the
optimization pipeline.
"""

from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.monitor_refresh_card import MonitorEmptyCard, MonitorRefreshCard
from src.gui.widgets.mouse_poll_card import MousePollCard
from src.gui.widgets.stat_card import STAT_CARDS, StatCard
from src.utils.debug_logger import get_debug_logger


class Dashboard(QWidget):
    """V2 dashboard: 4-col stat grid + temperature chart + USB polling widget."""

    monitor_fix_requested = Signal(str)  # = Signal()
    monitor_refresh_requested = Signal()

    # Re-broadcast of each poll snapshot — lets other views (the optimization
    # view's LiveStatRow) render the identical system stats as the dashboard.
    stats_ready = Signal(dict)

    thermal_retry_requested = Signal()  # Retry button -> StartupCoordinator relaunch

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Dashboard view")

        from src.gui.widgets.thermal_chart import ThermalChart

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 20)
        outer.setSpacing(12)

        # ── 4-col stat grid ─────────────────────────────────────────────
        grid_frame = QWidget()
        grid = QGridLayout(grid_frame)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self._cards: dict[str, StatCard] = {}
        for col, (key, label, tone) in enumerate(STAT_CARDS):
            card = StatCard(label, tone)
            self._cards[key] = card
            grid.addWidget(card, 0, col)

        outer.addWidget(grid_frame)

        # ── Temperature chart ────────────────────────────────────────────
        chart_wrap = QFrame()
        chart_wrap.setObjectName("chartWrap")
        chart_v = QVBoxLayout(chart_wrap)
        chart_v.setContentsMargins(0, 0, 0, 0)
        chart_v.setSpacing(0)

        chart_header = QFrame()
        chart_header.setObjectName("chartHeader")
        chart_hdr_layout = QHBoxLayout(chart_header)
        chart_hdr_layout.setContentsMargins(16, 10, 16, 8)

        chart_title_lbl = QLabel("TEMPERATURE HISTORY — LAST 60s")
        chart_title_lbl.setObjectName("chartTitle")
        chart_hdr_layout.addWidget(chart_title_lbl)
        chart_hdr_layout.addStretch()

        legend_cpu = QLabel("▬ CPU")
        legend_cpu.setObjectName("legendCpu")
        legend_gpu = QLabel("▬ GPU")
        legend_gpu.setObjectName("legendGpu")
        chart_hdr_layout.addWidget(legend_cpu)
        chart_hdr_layout.addSpacing(12)
        chart_hdr_layout.addWidget(legend_gpu)

        # Retry thermal monitoring without an app restart. Emits
        # thermal_retry_requested -> StartupCoordinator.on_thermal_retry_requested,
        # which relaunches the sidecar off the GUI thread. Styling (objectName)
        # is a DESIGN.md follow-up; default chrome is acceptable for v1.
        self._thermal_retry_btn = QPushButton("↻ Retry")
        self._thermal_retry_btn.setObjectName("thermalRetryBtn")
        self._thermal_retry_btn.clicked.connect(self.thermal_retry_requested)
        chart_hdr_layout.addSpacing(12)
        chart_hdr_layout.addWidget(self._thermal_retry_btn)

        chart_v.addWidget(chart_header)

        self.thermal_chart = ThermalChart()
        self.thermal_chart.set_offline("Thermal monitor not started")
        chart_v.addWidget(self.thermal_chart)

        outer.addWidget(chart_wrap)

        # ── Mouse polling card ──────────────────────────────────────────
        self._mouse_poll_card = MousePollCard(parent=self)
        outer.addWidget(self._mouse_poll_card)

        # ── Monitor refresh PRE-ALLOCATED slots ───────────────────────
        # Created here during Dashboard.__init__ alongside the stat tiles
        # / polling card / thermal chart — all of which parent correctly.
        # Dynamic creation later (via _on_finished during splash.exec()'s
        # nested event loop) fails to parent in the bundled PyInstaller
        # exe (3 rounds of evidence). Slots are hidden initially; one is
        # shown by set_monitor_data based on whether displays were
        # detected. Extras for displays 2..N go through dynamic creation.
        self._monitor_card_slot = MonitorRefreshCard(parent=self)
        self._monitor_card_slot.fix_requested.connect(self.monitor_fix_requested)
        self._monitor_card_slot.hide()
        outer.addWidget(self._monitor_card_slot)

        self._monitor_empty_slot = MonitorEmptyCard(parent=self)
        self._monitor_empty_slot.refresh_requested.connect(self.monitor_refresh_requested)
        self._monitor_empty_slot.hide()
        outer.addWidget(self._monitor_empty_slot)

        # Extras list (slots are separate). Uses indexOf(slot) at insert
        # time rather than a cached index, so it's robust to layout
        # mutations elsewhere.
        self._outer_layout = outer
        self._monitor_cards: list = []

        outer.addStretch(1)

        self._worker_thread: QThread | None = None
        self._worker = None  # SystemStatsWorker — lazily created in start_polling()
        self._apply_count: int = 0
        self._log = get_debug_logger()

    # ── Polling lifecycle ──────────────────────────────────────────────

    def start_polling(self) -> None:
        from src.gui.worker import SystemStatsWorker
        if self._worker is not None:
            self._log.info("Dashboard.start_polling: already running, skipping")
            return
        self._log.info("Dashboard.start_polling: spawning shared system-stats worker thread")
        self._worker_thread = QThread(self)
        self._worker_thread.setObjectName("SystemStatsPoll")
        self._worker = SystemStatsWorker()
        self._worker.moveToThread(self._worker_thread)
        self._worker.snapshot_ready.connect(self.apply_snapshot)
        self._worker_thread.finished.connect(self._worker.deleteLater)
        self._worker_thread.started.connect(self._worker.start)
        self._worker_thread.start()
        self._log.info("Dashboard.start_polling: worker thread started (isRunning=%s)",
                 self._worker_thread.isRunning())

    def set_thermal_retry_enabled(self, enabled: bool) -> None:
        """Enable/disable the thermal Retry button (disabled while a retry runs)."""
        self._thermal_retry_btn.setEnabled(enabled)

    def stop_polling(self) -> None:
        if self._worker is None or self._worker_thread is None:
            return
        # Stop by ending the worker thread's event loop — that halts the
        # worker's QTimer on its own thread. Stopping the timer directly from
        # here (the GUI thread) would be a cross-thread violation, so the
        # worker exposes no stop() and we deliberately do not call one.
        self._worker_thread.quit()
        self._worker_thread.wait(1000)
        self._worker = None
        self._worker_thread = None

    # ── Render slot ────────────────────────────────────────────────────

    def apply_snapshot(self, snapshot: dict) -> None:
        self._apply_count += 1
        if self._apply_count <= 3 or self._apply_count % 12 == 0:
            self._log.info(
                "Dashboard.apply_snapshot #%d: cpu_temp=%s gpu_temp=%s _cpu_c=%s _gpu_c=%s",
                self._apply_count,
                snapshot.get("cpu_temp"),
                snapshot.get("gpu_temp"),
                snapshot.get("_cpu_c"),
                snapshot.get("_gpu_c"),
            )
        for key, card in self._cards.items():
            card.set_value(str(snapshot.get(key, "—")))
        # Mouse polling tile owns its own manual-measurement guard.
        self._mouse_poll_card.apply_snapshot(snapshot)
        # Feed thermal chart
        cpu_c = snapshot.get("_cpu_c")
        gpu_c = snapshot.get("_gpu_c")
        if cpu_c is not None or gpu_c is not None:
            self.thermal_chart.append_sample(cpu_c, gpu_c)
        # Re-broadcast to any extra subscriber views (the optimization view's
        # LiveStatRow) so every view renders the identical snapshot.
        self.stats_ready.emit(snapshot)

    def receive_poll_result(self, result: dict) -> None:
        """Feed a pipeline-measured poll result to the mouse poll card."""
        self._mouse_poll_card.apply_pipeline_result(result)

    def set_monitor_data(self, displays: list[dict]) -> None:
        """Show/hide pre-allocated slots; dynamically build extras for 2+ monitors.

        Primary card uses the slot allocated in __init__ (parents correctly).
        Extras for displays 2..N go through dynamic insertion — known to be
        fragile in the bundled PyInstaller exe but tolerable when caller
        defers this until after main.show().
        """
        self._log.info("Dashboard.set_monitor_data: %d display(s) received", len(displays or []))

        # Diagnostic: confirm dashboard widget state at call time
        self._log.info(
            "Dashboard: self.parent()=%s self.parentWidget()=%s layout_is_outer=%s",
            type(self.parent()).__name__ if self.parent() else "None",
            type(self.parentWidget()).__name__ if self.parentWidget() else "None",
            self.layout() is self._outer_layout,
        )

        self._rebuild_monitor_cards(displays)

        # Force layout + style recompute (belt-and-suspenders)
        self.updateGeometry()
        if self.layout() is not None:
            self.layout().activate()
        self._monitor_card_slot.ensurePolished()
        self._monitor_empty_slot.ensurePolished()

        self._log_geometry("immediate")
        # 3-arg singleShot: when ``self`` (the context QObject) is destroyed
        # before the 500 ms elapses, Qt auto-cancels the deferred slot. The
        # bound method reference avoids a closure-captured ``self`` and keeps
        # the slot identity stable for any future disconnect.
        QTimer.singleShot(500, self, self._log_geometry_deferred)

    def _log_geometry_deferred(self) -> None:
        """Trampoline so ``set_monitor_data`` can pass a bound method to
        ``QTimer.singleShot`` instead of a closure."""
        self._log_geometry("deferred")

    def _rebuild_monitor_cards(self, displays: list[dict]) -> None:
        """Show/hide the pre-allocated slots and (re)build extras for 2+ monitors."""
        # Tear down extras from prior calls (slots survive)
        for extra in self._monitor_cards:
            self._outer_layout.removeWidget(extra)
            extra.deleteLater()
        self._monitor_cards = []

        if not displays:
            self._monitor_card_slot.hide()
            self._monitor_empty_slot.show()
            self._log.info("Dashboard: showing pre-allocated MonitorEmptyCard slot")
            return

        self._monitor_empty_slot.hide()
        self._monitor_card_slot.set_display(displays[0])
        self._monitor_card_slot.show()
        self._log.info("Dashboard: showing pre-allocated MonitorRefreshCard slot for %s",
                 displays[0].get("device"))

        # Extras (displays 2..N) — dynamic. Use indexOf(slot) so we're
        # position-independent even if other widgets shift around.
        base_idx = self._outer_layout.indexOf(self._monitor_card_slot)
        for offset, d in enumerate(displays[1:], start=1):
            card = MonitorRefreshCard(parent=self)
            card.set_display(d)
            card.fix_requested.connect(self.monitor_fix_requested)
            self._outer_layout.insertWidget(base_idx + offset, card)
            if card.parentWidget() is not self:
                card.setParent(self)
            self._monitor_cards.append(card)
            self._log.info("Dashboard: extra card[%d] %s parent=%s",
                     offset, d.get("device"),
                     type(card.parentWidget()).__name__ if card.parentWidget() else "None")

    def _log_geometry(self, tag: str) -> None:
        """Diagnostic dump of monitor-card geometry / parenting state."""
        try:
            for slot_name, c in (("slot_card", self._monitor_card_slot),
                                 ("slot_empty", self._monitor_empty_slot)):
                self._log.info(
                    "Dashboard[%s]: %s sz=%dx%d hint=%dx%d visible=%s hidden=%s parent=%s",
                    tag, slot_name,
                    c.size().width(), c.size().height(),
                    c.sizeHint().width(), c.sizeHint().height(),
                    c.isVisible(), c.isHidden(),
                    type(c.parentWidget()).__name__ if c.parentWidget() else "None",
                )
            for i, c in enumerate(self._monitor_cards):
                self._log.info(
                    "Dashboard[%s]: extra[%d] %s sz=%dx%d visible=%s parent=%s",
                    tag, i, type(c).__name__,
                    c.size().width(), c.size().height(),
                    c.isVisible(),
                    type(c.parentWidget()).__name__ if c.parentWidget() else "None",
                )
        except Exception as exc:
            self._log.warning("Dashboard: geometry-log[%s] failed: %s", tag, exc)
