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
from src.gui.widgets.nvidia_dlss_card import NvidiaDlssCard
from src.gui.widgets.nvidia_profile_card import NvidiaProfileCard
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

    # Apply-button request from either NVIDIA card; carries the fix check name
    # ("nvidia_dlss_preset" or "nvidia_profile"). Bubbled to StartupCoordinator.
    nvidia_fix_requested = Signal(str)

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
        # which relaunches the sidecar off the GUI thread. Hidden by default --
        # only shown (via set_thermal_retry_visible) when the LHM sidecar fails
        # to load temps; invisible whenever thermal monitoring is healthy.
        self._thermal_retry_btn = QPushButton("↻ Retry")
        self._thermal_retry_btn.setObjectName("thermalRetryBtn")
        self._thermal_retry_btn.clicked.connect(self.thermal_retry_requested)
        self._thermal_retry_btn.hide()
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

        # ── NVIDIA driver-profile cards (DLSS preset + full profile) ─────
        # Pre-allocated here (like the monitor slots below) because dynamic
        # creation during the splash's nested event loop fails to parent in the
        # bundled PyInstaller exe. Hidden until set_nvidia_data shows them when
        # nvidia-smi detects a GPU and NPI.exe is available.
        self._nvidia_dlss_card = NvidiaDlssCard("DLSS Preset", "Apply Preset", parent=self)
        self._nvidia_dlss_card.apply_requested.connect(self.nvidia_fix_requested)
        self._nvidia_dlss_card.priority_changed.connect(self._on_dlss_priority_changed)
        self._nvidia_dlss_card.hide()
        outer.addWidget(self._nvidia_dlss_card)

        self._nvidia_full_card = NvidiaProfileCard(
            "nvidia_profile", "NVIDIA Driver Profile", "Optimize", parent=self
        )
        self._nvidia_full_card.apply_requested.connect(self.nvidia_fix_requested)
        self._nvidia_full_card.hide()
        outer.addWidget(self._nvidia_full_card)

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

    def set_thermal_retry_visible(self, visible: bool) -> None:
        """Show/hide the thermal Retry button.

        The button only makes sense when the LHM sidecar failed to load temps,
        so it stays invisible whenever thermal monitoring is healthy. Called by
        StartupCoordinator after the initial sidecar attempt and after each
        retry resolves.
        """
        self._thermal_retry_btn.setVisible(visible)

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

    def set_nvidia_data(self, nvidia) -> None:
        """Show/populate the NVIDIA fix cards based on nvidia-smi detection.

        Shows the full-profile card whenever an NVIDIA GPU is detected and NPI is
        available; shows the DLSS-preset card only when the GPU resolves to a
        supported preset (``dlss_presets.get_preset``). The recommendation reflects
        GPU 0 + ``config.nvidia.dlss.priority`` (NPI applies the profile globally,
        not per-GPU).
        """
        from src.config import config
        from src.llm.action_proposer import propose_for_check
        from src.utils.dlss_presets import get_preset
        from src.utils.nvidia_npi import find_npi_exe

        # Detection: a non-empty list means nvidia-smi returned GPU(s); a dict
        # ({"error": ...}) or empty list means not detected. NPI must also be
        # present or the fix can neither run nor be reverted -- don't offer it.
        if not isinstance(nvidia, list) or not nvidia or find_npi_exe() is None:
            self._nvidia_dlss_card.hide()
            self._nvidia_full_card.hide()
            self._nvidia_gpu_name = None
            self._log.info("Dashboard.set_nvidia_data: hidden (no NVIDIA GPU or NPI absent)")
            return

        gpu_name = str(nvidia[0].get("GPU") or "NVIDIA GPU")
        self._nvidia_gpu_name = gpu_name

        # Full-profile card: valid for any detected NVIDIA GPU.
        full_prop = propose_for_check("nvidia_profile") or {}
        self._nvidia_full_card.set_gpu(
            gpu_name,
            "Optimize: G-Sync · VSync · FPS cap · ReBar · DLSS · Power",
            full_prop.get("explanation", ""),
        )
        self._nvidia_full_card.show()

        # DLSS card: only when the GPU resolves to a supported preset. classify()
        # rejects GTX / workstation (RTX A / Ada Generation / Quadro / Titan) and
        # unmapped generations, so get_preset() returns None -> card hidden.
        preset = get_preset(gpu_name)
        if preset is not None:
            self._nvidia_dlss_card.set_priority(config.nvidia.dlss.priority)
            self._nvidia_dlss_card.set_gpu(
                gpu_name,
                f"Recommended: DLSS Preset {preset.letter}",
                self._dlss_tooltip(preset),
            )
            self._nvidia_dlss_card.show()
            self._log.info("Dashboard.set_nvidia_data: DLSS card shown (%s -> Preset %s, %s)",
                           preset.tier, preset.letter, preset.priority)
        else:
            self._nvidia_dlss_card.hide()
            self._log.info("Dashboard.set_nvidia_data: DLSS card hidden (%s unsupported)", gpu_name)

    def _dlss_tooltip(self, preset) -> str:
        """E1: explain the recommended preset (model + quality/FPS lean + RT caveat)."""
        return (
            f"{preset.model_name}\n"
            f"Lean: {preset.priority} "
            "(Quality=M / FPS=L on RTX 40/50; K on RTX 20/30).\n"
            "Note: in some ray-traced games Preset K (DLSS 4) can look better than "
            "M/L if the game's denoiser interacts poorly -- override per-game if needed."
        )

    def _on_dlss_priority_changed(self, priority: str) -> None:
        """DLSS card quality/FPS toggle: update live config, persist, re-render."""
        if priority not in ("quality", "fps"):
            return
        from src.config import config
        from src.utils.dlss_presets import get_preset

        config.nvidia.dlss.priority = priority
        try:
            from PySide6.QtCore import QSettings
            QSettings("lil_bro", "GUI").setValue("dlss/priority", priority)
        except Exception:
            self._log.warning("DLSS priority QSettings write failed", exc_info=True)

        gpu_name = getattr(self, "_nvidia_gpu_name", None)
        if not gpu_name:
            return
        preset = get_preset(gpu_name, priority)
        if preset is not None:
            self._nvidia_dlss_card.set_gpu(
                gpu_name,
                f"Recommended: DLSS Preset {preset.letter}",
                self._dlss_tooltip(preset),
            )
        self._log.info("DLSS priority -> %s (preset %s)", priority,
                       preset.letter if preset else "none")

    def seed_dlss_priority(self, specs: dict) -> None:
        """E2: seed config.nvidia.dlss.priority at startup, before set_nvidia_data.

        Precedence: manual QSettings toggle > monitor-aware (primary display) >
        lil_bro_config.json > "quality". A stored manual choice always wins.
        """
        from src.config import config
        from src.utils.dlss_presets import resolve_startup_priority

        manual = None
        try:
            from PySide6.QtCore import QSettings
            stored = QSettings("lil_bro", "GUI").value("dlss/priority", None)
            if stored in ("quality", "fps"):
                manual = stored
        except Exception:
            self._log.warning("DLSS priority QSettings read failed", exc_info=True)

        config.nvidia.dlss.priority = resolve_startup_priority(specs, manual)
        self._log.info("DLSS priority seeded -> %s", config.nvidia.dlss.priority)

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
