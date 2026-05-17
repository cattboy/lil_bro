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
from PySide6.QtWidgets import QHBoxLayout, QPushButton  # noqa: E402

# Top-level import so PyInstaller's static analyzer picks up both card classes
# (the previous lazy import inside set_monitor_data could be missed by modulegraph).
from src.gui.widgets.monitor_refresh_card import MonitorRefreshCard, MonitorEmptyCard  # noqa: E402


_CARDS = (
    ("cpu_usage", "CPU USAGE", "norm"),
    ("cpu_temp",  "CPU TEMP",  "warn"),
    ("gpu_temp",  "GPU TEMP",  "ok"),
    ("ram_used",  "RAM USED",  "cyan"),
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
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()
        log.info("DashboardWorker.start: entering on thread %s",
                 QThread.currentThread().objectName() or "<unnamed>")
        try:
            import psutil
            psutil.cpu_percent(interval=None)  # prime baseline so first real tick isn't 0%
        except Exception:
            pass
        if self._timer is None:
            self._timer = QTimer()
            self._timer.timeout.connect(self._tick)
            self._timer.start(_POLL_INTERVAL_MS)
        log.info("DashboardWorker.start: timer armed, firing first tick now")
        self._tick()  # immediate first sample  # immediate first sample

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
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()
        try:
            snap = dict(quick_status_snapshot(self._lhm))
        except Exception:
            snap = {}

        # Augment with cpu_usage and ram_used via psutil
        try:
            import psutil
            snap["cpu_usage"] = f"{psutil.cpu_percent(interval=None):.0f}%"
            vm = psutil.virtual_memory()
            snap["ram_used"] = f"{vm.used / 1_073_741_824:.1f} GB"
        except Exception:
            snap.setdefault("cpu_usage", "—")
            snap.setdefault("ram_used", "—")

        # Thermal data from fetch_snapshot — same source the chart uses, so always accurate.
        # Also overrides cpu_temp/gpu_temp from quick_status_snapshot (which calls
        # lhm.read_latest(), a method LHMSidecar does not implement).
        therm: dict = {}
        try:
            from src.agent_tools.thermal_guidance import derive_cpu_temp, derive_gpu_temp
            from src.benchmarks.thermal_monitor import fetch_snapshot
            therm = fetch_snapshot()
            if therm:
                cpu_c_f = derive_cpu_temp(therm)
                gpu_c_f = derive_gpu_temp(therm)
                if cpu_c_f is not None:
                    snap["_cpu_c"] = cpu_c_f
                    snap["cpu_temp"] = f"{int(round(cpu_c_f))}°C"
                if gpu_c_f is not None:
                    snap["_gpu_c"] = gpu_c_f
                    snap["gpu_temp"] = f"{int(round(gpu_c_f))}°C"
        except Exception as exc:
            log.warning("DashboardWorker._tick: thermal fetch failed: %s", exc, exc_info=True)

        # Diagnostic INFO on first 3 ticks and every 12th (≈ 1 min) — keeps
        # the log compact but proves the polling loop is alive and surfaces
        # what fetch_snapshot is returning vs. what derive_*_temp extracted.
        self._tick_count = getattr(self, "_tick_count", 0) + 1
        if self._tick_count <= 3 or self._tick_count % 12 == 0:
            sample_keys = list(therm.keys())[:3] if therm else []
            log.info(
                "DashboardWorker._tick #%d: therm_keys=%d sample=%s cpu_c=%s gpu_c=%s cpu_temp=%s",
                self._tick_count,
                len(therm),
                sample_keys,
                snap.get("_cpu_c"),
                snap.get("_gpu_c"),
                snap.get("cpu_temp"),
            )

        self.snapshot_ready.emit(snap)


class _DashboardCard(QFrame):
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


class Dashboard(QWidget):
    """V2 dashboard: 4-col stat grid + temperature chart + USB polling widget."""

    monitor_fix_requested = Signal(str)  # = Signal()
    monitor_refresh_requested = Signal()

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

        self._cards: dict[str, _DashboardCard] = {}
        for col, (key, label, tone) in enumerate(_CARDS):
            card = _DashboardCard(label, tone)
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

        chart_v.addWidget(chart_header)

        self.thermal_chart = ThermalChart()
        self.thermal_chart.set_offline("Thermal monitor not started")
        chart_v.addWidget(self.thermal_chart)

        outer.addWidget(chart_wrap)

        # ── USB polling widget ───────────────────────────────────────────
        poll_frame = QFrame()
        poll_frame.setObjectName("pollWidget")
        poll_h = QHBoxLayout(poll_frame)
        poll_h.setContentsMargins(20, 16, 20, 16)

        poll_left = QVBoxLayout()
        poll_left.setSpacing(4)

        poll_label = QLabel("USB POLLING RATE")
        poll_label.setObjectName("pollLabel")
        poll_left.addWidget(poll_label)

        hz_row = QHBoxLayout()
        hz_row.setSpacing(4)
        self._poll_val = QLabel("—")
        self._poll_val.setObjectName("pollValue")
        self._poll_unit = QLabel("Hz")
        self._poll_unit.setObjectName("pollUnit")
        hz_row.addWidget(self._poll_val)
        hz_row.addWidget(self._poll_unit)
        hz_row.addStretch()
        poll_left.addLayout(hz_row)

        self._poll_status = QLabel("Not measured")
        self._poll_status.setObjectName("pollStatus")
        poll_left.addWidget(self._poll_status)

        poll_h.addLayout(poll_left)
        poll_h.addStretch()

        self._poll_btn = QPushButton("Test Polling")
        self._poll_btn.setObjectName("secondary")
        self._poll_btn.setFixedWidth(120)
        self._poll_btn.clicked.connect(self._manual_poll)
        poll_h.addWidget(self._poll_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

        outer.addWidget(poll_frame)

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
        self._worker: DashboardWorker | None = None

    # ── USB polling ────────────────────────────────────────────────────

    def _manual_poll(self) -> None:
        """Force an immediate snapshot tick to refresh the polling rate display."""
        self._poll_btn.setEnabled(False)
        self._poll_status.setText("Measuring…")
        try:
            snap = quick_status_snapshot(
                self._worker._lhm if self._worker else None
            )
            hz_str = snap.get("mouse_hz", "")
            self._update_poll_display(hz_str)
        except Exception:
            self._poll_status.setText("Measurement failed")
        finally:
            self._poll_btn.setEnabled(True)

    def _update_poll_display(self, hz_str: str) -> None:
        try:
            hz = int(float(hz_str.replace(" Hz", "").replace("Hz", "")))
            self._poll_val.setText(str(hz))
            quality = "Excellent" if hz >= 1000 else "Good" if hz >= 500 else "Low"
            self._poll_status.setText(quality)
        except (ValueError, AttributeError):
            self._poll_val.setText("—")
            self._poll_status.setText("Not measured")

    # ── Polling lifecycle ──────────────────────────────────────────────

    def start_polling(self, lhm=None) -> None:
        from src.utils.debug_logger import get_debug_logger
        log = get_debug_logger()
        if self._worker is not None:
            log.info("Dashboard.start_polling: already running, skipping")
            return
        log.info(
            "Dashboard.start_polling: spawning worker thread (lhm=%s)",
            "yes" if lhm else "no",
        )
        self._worker_thread = QThread(self)
        self._worker_thread.setObjectName("DashboardPoll")
        self._worker = DashboardWorker()
        self._worker.set_lhm(lhm)
        self._worker.moveToThread(self._worker_thread)
        self._worker.snapshot_ready.connect(self.apply_snapshot)
        self._worker_thread.started.connect(self._worker.start)
        self._worker_thread.start()
        log.info("Dashboard.start_polling: worker thread started (isRunning=%s)",
                 self._worker_thread.isRunning())

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
        self._apply_count = getattr(self, "_apply_count", 0) + 1
        if self._apply_count <= 3 or self._apply_count % 12 == 0:
            from src.utils.debug_logger import get_debug_logger
            log = get_debug_logger()
            log.info(
                "Dashboard.apply_snapshot #%d: cpu_temp=%s gpu_temp=%s _cpu_c=%s _gpu_c=%s",
                self._apply_count,
                snapshot.get("cpu_temp"),
                snapshot.get("gpu_temp"),
                snapshot.get("_cpu_c"),
                snapshot.get("_gpu_c"),
            )
        for key, card in self._cards.items():
            card.set_value(str(snapshot.get(key, "—")))
        # Update poll display from snapshot data
        hz_str = snapshot.get("mouse_hz", "")
        if hz_str and hz_str != "—":
            self._update_poll_display(hz_str)
        # Feed thermal chart
        cpu_c = snapshot.get("_cpu_c")
        gpu_c = snapshot.get("_gpu_c")
        if cpu_c is not None or gpu_c is not None:
            self.thermal_chart.append_sample(cpu_c, gpu_c)

    def set_monitor_data(self, displays: list[dict]) -> None:
        """Show/hide pre-allocated slots; dynamically build extras for 2+ monitors.

        Primary card uses the slot allocated in __init__ (parents correctly).
        Extras for displays 2..N go through dynamic insertion — known to be
        fragile in the bundled PyInstaller exe but tolerable when caller
        defers this until after main.show().
        """
        from src.utils.debug_logger import get_debug_logger
        from PySide6.QtCore import QTimer
        log = get_debug_logger()
        log.info("Dashboard.set_monitor_data: %d display(s) received", len(displays or []))

        # Diagnostic: confirm dashboard widget state at call time
        log.info(
            "Dashboard: self.parent()=%s self.parentWidget()=%s layout_is_outer=%s",
            type(self.parent()).__name__ if self.parent() else "None",
            type(self.parentWidget()).__name__ if self.parentWidget() else "None",
            self.layout() is self._outer_layout,
        )

        # Tear down extras from prior calls (slots survive)
        for extra in self._monitor_cards:
            self._outer_layout.removeWidget(extra)
            extra.deleteLater()
        self._monitor_cards = []

        if not displays:
            self._monitor_card_slot.hide()
            self._monitor_empty_slot.show()
            log.info("Dashboard: showing pre-allocated MonitorEmptyCard slot")
        else:
            self._monitor_empty_slot.hide()
            self._monitor_card_slot.set_display(displays[0])
            self._monitor_card_slot.show()
            log.info("Dashboard: showing pre-allocated MonitorRefreshCard slot for %s",
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
                log.info("Dashboard: extra card[%d] %s parent=%s",
                         offset, d.get("device"),
                         type(card.parentWidget()).__name__ if card.parentWidget() else "None")

        # Force layout + style recompute (belt-and-suspenders)
        self.updateGeometry()
        if self.layout() is not None:
            self.layout().activate()
        self._monitor_card_slot.ensurePolished()
        self._monitor_empty_slot.ensurePolished()

        def _log_geometry(tag: str) -> None:
            try:
                for slot_name, c in (("slot_card", self._monitor_card_slot),
                                     ("slot_empty", self._monitor_empty_slot)):
                    log.info(
                        "Dashboard[%s]: %s sz=%dx%d hint=%dx%d visible=%s hidden=%s parent=%s",
                        tag, slot_name,
                        c.size().width(), c.size().height(),
                        c.sizeHint().width(), c.sizeHint().height(),
                        c.isVisible(), c.isHidden(),
                        type(c.parentWidget()).__name__ if c.parentWidget() else "None",
                    )
                for i, c in enumerate(self._monitor_cards):
                    log.info(
                        "Dashboard[%s]: extra[%d] %s sz=%dx%d visible=%s parent=%s",
                        tag, i, type(c).__name__,
                        c.size().width(), c.size().height(),
                        c.isVisible(),
                        type(c.parentWidget()).__name__ if c.parentWidget() else "None",
                    )
            except Exception as exc:
                log.warning("Dashboard: geometry-log[%s] failed: %s", tag, exc)

        _log_geometry("immediate")
        QTimer.singleShot(500, self, lambda: _log_geometry("deferred"))
