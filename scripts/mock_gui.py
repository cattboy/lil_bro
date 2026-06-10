"""Developer-only mock GUI for inspecting dashboard card layouts.

Launches the REAL MainWindow + Dashboard with the production theme, populated
entirely from scripts/mock_fixtures.py — no LHM sidecar, no nvidia-smi, no
subprocesses, no registry writes. A floating "Mock Controls" panel flips each
card between its visual states and applies whole scenarios.

Run from the repo root (venv active):

    python scripts/mock_gui.py
    python scripts/mock_gui.py --smoke   # headless-friendly auto-cycle + exit

Monkeypatches (script-level only; production code untouched):
  * src.utils.nvidia_npi.find_npi_exe — canned path/None so the NVIDIA cards
    show/hide deterministically (the "NPI available" checkbox).
  * src.gui.worker._MousePollWorker — fake worker so the card's real
    "Test Polling" button shows the genuine in-flight state, then lands a
    canned result (no 2 s cursor sampling).

One private-attr helper: mock_fixtures.reset_mouse_card restores the
MousePollCard "Not measured" state (no public reset exists).

Accepted benign side effects (same as the real app): ./lil_bro/ dir creation
on nvidia_npi import; QSettings "dlss/priority" write if the DLSS Quality/FPS
toggle is clicked.

Notes: the WASD filter is app-global (installed by MainWindow), so W/S
keypresses on the controls panel are eaten — drive the panel with the mouse.
The sidebar's "2"/Start button switches to the (blank, unwired) pipeline view;
press "1" to return to the Dashboard.
"""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # CWD-relative paths (./lil_bro, lil_bro_config.json) behave like the real app

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from scripts import mock_fixtures as fx
from src.agent_tools.nvidia_profile import analyze_nvidia_profile
from src.gui import theme
from src.gui.windows.main_window import MainWindow

_FAKE_NPI_PATH = r"C:\mock\nvidiaProfileInspector.exe"


# ── Monkeypatches ───────────────────────────────────────────────────────────


class FakeMousePollWorker(QObject):
    """Stands in for src.gui.worker._MousePollWorker (2 s cursor sampler).

    The card spawns it on a QThread whose event loop runs after ``run()``
    returns, so the singleShot fires on that thread and the canned result is
    delivered through the card's real finished-signal wiring.
    """

    finished = Signal(dict)
    canned: dict = dict(fx.MOUSE_RESULTS["ok_1000"])

    def run(self) -> None:
        QTimer.singleShot(1500, lambda: self.finished.emit(dict(type(self).canned)))


def set_npi_available(available: bool) -> None:
    """Patch find_npi_exe; set_nvidia_data re-imports it per call, so a plain
    module setattr is picked up by the next apply."""
    import src.utils.nvidia_npi as nvidia_npi
    nvidia_npi.find_npi_exe = (lambda: _FAKE_NPI_PATH) if available else (lambda: None)


def apply_monkeypatches() -> None:
    set_npi_available(True)
    import src.gui.worker as worker
    worker._MousePollWorker = FakeMousePollWorker


# ── Driver: fixtures -> the Dashboard's real public population APIs ─────────


class MockDriver:
    """Applies fixture states through the same entry points the real app uses,
    and stands in for StartupCoordinator on the dashboard's fix/refresh/retry
    signals (all same-thread; no workers are ever spawned)."""

    def __init__(self, main: MainWindow) -> None:
        self.main = main
        self.dashboard = main._dashboard
        self.panel: MockControls | None = None

        self._monitor_key = "optimal"
        self._displays: list[dict] = fx.displays("optimal")
        self._anim_base = fx.ANIM_BASES["normal"]
        self._anim_phase = 0
        self._anim_timer = QTimer(main)
        self._anim_timer.setInterval(1000)
        self._anim_timer.timeout.connect(self._anim_tick)

        d = self.dashboard
        d.monitor_fix_requested.connect(self._on_monitor_fix)
        d.monitor_refresh_requested.connect(self._on_monitor_refresh)
        d.nvidia_fix_requested.connect(self._on_nvidia_fix)
        d.thermal_retry_requested.connect(self._on_thermal_retry)

    # ── State appliers ──────────────────────────────────────────────────

    def apply_stats(self, key: str) -> None:
        self._anim_base = fx.ANIM_BASES.get(key, fx.ANIM_BASES["normal"])
        self.dashboard.apply_snapshot(dict(fx.SNAPSHOTS[key]))

    def apply_thermal(self, key: str) -> None:
        chart = self.dashboard.thermal_chart
        chart.clear_samples()
        if key == "offline":
            self.set_animation(False)
            chart.set_offline("Thermal monitor offline — LHM sidecar failed (mock)")
            self.dashboard.set_thermal_retry_visible(True)
            return
        for cpu, gpu in fx.thermal_series(key):
            chart.append_sample(cpu, gpu)
        self.dashboard.set_thermal_retry_visible(False)

    def apply_mouse(self, key: str) -> None:
        card = self.dashboard._mouse_poll_card
        if key == "not_measured":
            fx.reset_mouse_card(card)
        elif key == "measuring":
            FakeMousePollWorker.canned = dict(fx.MOUSE_RESULTS["ok_1000"])
            card._poll_btn.click()  # real button -> genuine in-flight UI -> fake worker
        else:
            self.dashboard.receive_poll_result(dict(fx.MOUSE_RESULTS[key]))

    def apply_monitors(self, key: str) -> None:
        self._monitor_key = key
        self._displays = fx.displays(key)
        self.dashboard.set_monitor_data(self._displays)

    def apply_nvidia(self, key: str) -> None:
        # Seed first: get_preset() inside nvidia_specs("ok") must resolve the
        # same priority the analyzer will use, or the "ok" fixture renders as
        # WARNING. Then rebuild specs with the seeded priority. Order below
        # mirrors app.py run(): seed -> set_nvidia_data -> findings.
        self.dashboard.seed_dlss_priority(fx.nvidia_specs(key))
        specs = fx.nvidia_specs(key)
        self.dashboard.set_nvidia_data(specs.get("NVIDIA") or [])
        self.dashboard.set_nvidia_profile_findings(analyze_nvidia_profile(specs))

    def apply_scenario(self, name: str) -> None:
        sc = fx.SCENARIOS[name]
        self.apply_stats(sc["stats"])
        self.apply_thermal(sc["thermal"])
        self.apply_mouse(sc["mouse"])
        self.apply_monitors(sc["monitors"])
        self.apply_nvidia(sc["nvidia"])
        self.set_animation(sc["animate"])

    def set_animation(self, on: bool) -> None:
        if on:
            self._anim_timer.start()
        else:
            self._anim_timer.stop()
        if self.panel is not None:
            self.panel.sync_animate(on)

    def _anim_tick(self) -> None:
        self._anim_phase += 1
        p = self._anim_phase
        base_cpu, base_gpu = self._anim_base
        cpu = base_cpu + 6.0 * math.sin(p / 7.0)
        gpu = base_gpu + 5.0 * math.sin(p / 9.0 + 2.0)
        usage = max(1.0, 25.0 + 20.0 * math.sin(p / 5.0))
        ram = 16.0 + 2.0 * math.sin(p / 11.0)
        self.dashboard.apply_snapshot({
            "cpu_usage": f"{usage:.0f}%",
            "cpu_temp": f"{cpu:.0f}°C",
            "gpu_temp": f"{gpu:.0f}°C",
            "ram_used": f"{ram:.1f} GB",
            "_cpu_c": round(cpu, 1),
            "_gpu_c": round(gpu, 1),
        })

    # ── Mock stand-ins for StartupCoordinator's fix/refresh/retry flows ─

    def _on_monitor_fix(self, device: str) -> None:
        print(f"[mock] monitor fix requested for {device} — applying in 800 ms")
        for d in self._displays:
            if d.get("device") == device and d.get("max_refresh_hz"):
                d["current_refresh_hz"] = d["max_refresh_hz"]
        # Mirrors the real coordinator's post-fix re-probe -> set_monitor_data.
        QTimer.singleShot(800, lambda: self.dashboard.set_monitor_data(self._displays))

    def _on_monitor_refresh(self) -> None:
        if self._monitor_key == "empty":
            print("[mock] monitor refresh — simulating a re-probe that finds a display")
            if self.panel is not None:
                self.panel.sync_monitor_combo("suboptimal")
            self.apply_monitors("suboptimal")
        else:
            self.apply_monitors(self._monitor_key)

    def _on_nvidia_fix(self, check_name: str) -> None:
        if check_name == "nvidia_profile":
            print("[mock] nvidia_profile fix requested — flipping to OK in 800 ms")
            # Replicates StartupCoordinator._on_nvidia_fix_result success path,
            # exercising the _nvidia_last_expected fallback render.
            QTimer.singleShot(
                800,
                lambda: self.dashboard.set_nvidia_profile_findings({"status": "OK"}),
            )
        else:
            print(f"[mock] {check_name} apply requested (no card change in the real app)")

    def _on_thermal_retry(self) -> None:
        print("[mock] thermal retry — simulating a successful sidecar relaunch")
        if self.panel is not None:
            self.panel.sync_thermal_combo("normal")
        self.apply_thermal("normal")
        self.set_animation(True)


# ── Floating controls panel ─────────────────────────────────────────────────


class MockControls(QWidget):
    """Always-on-top tool window: scenario presets + per-card state combos."""

    def __init__(self, driver: MockDriver) -> None:
        super().__init__()
        self.driver = driver
        driver.panel = self
        self.setWindowTitle("Mock Controls")
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedWidth(300)
        c = theme.COLORS
        self.setStyleSheet(
            f"QWidget {{ background: {c['deep']}; }}"
            f"QLabel {{ color: {c['text_secondary']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # Scenario preset row
        root.addWidget(QLabel("SCENARIO"))
        row = QHBoxLayout()
        self._scenario = QComboBox()
        self._scenario.addItems(list(fx.SCENARIOS))
        row.addWidget(self._scenario, 1)
        apply_btn = QPushButton("Apply")
        apply_btn.setObjectName("secondary")
        apply_btn.setAutoDefault(False)
        apply_btn.setDefault(False)
        apply_btn.clicked.connect(self._on_apply_scenario)
        row.addWidget(apply_btn)
        root.addLayout(row)

        # Per-card combos
        self._stats = self._combo(root, "Stats", list(fx.SNAPSHOTS), driver.apply_stats)
        self._thermal = self._combo(
            root, "Thermal", ["normal", "warning", "critical", "offline"], driver.apply_thermal
        )
        self._mouse = self._combo(
            root, "Mouse", ["not_measured", *fx.MOUSE_RESULTS, "measuring"], driver.apply_mouse
        )
        self._monitors = self._combo(root, "Monitors", list(fx.DISPLAYS), driver.apply_monitors)
        self._nvidia = self._combo(
            root, "NVIDIA", ["ok", "warning", "gtx_no_dlss", "no_gpu"], driver.apply_nvidia
        )

        # Toggles
        self._animate = QCheckBox("Animate stats/thermal (1 Hz)")
        self._animate.toggled.connect(self._on_animate_toggled)
        root.addWidget(self._animate)

        self._npi = QCheckBox("NPI available (NVIDIA cards)")
        self._npi.setChecked(True)
        self._npi.toggled.connect(self._on_npi_toggled)
        root.addWidget(self._npi)

        root.addStretch(1)

    def _combo(self, layout, label: str, items: list[str], applier) -> QComboBox:
        layout.addWidget(QLabel(label.upper()))
        box = QComboBox()
        box.addItems(items)
        box.currentTextChanged.connect(applier)
        layout.addWidget(box)
        return box

    # ── Handlers ────────────────────────────────────────────────────────

    def _on_apply_scenario(self) -> None:
        name = self._scenario.currentText()
        sc = fx.SCENARIOS[name]
        # Sync combos silently, then apply once through the driver — avoids
        # five redundant cascading applies from currentTextChanged.
        for box, key in (
            (self._stats, "stats"), (self._thermal, "thermal"), (self._mouse, "mouse"),
            (self._monitors, "monitors"), (self._nvidia, "nvidia"),
        ):
            self._set_silently(box, sc[key])
        self.driver.apply_scenario(name)

    def _on_animate_toggled(self, on: bool) -> None:
        self.driver.set_animation(on)

    def _on_npi_toggled(self, available: bool) -> None:
        set_npi_available(available)
        self.driver.apply_nvidia(self._nvidia.currentText())

    # ── Driver-initiated sync (blockSignals so applies don't double-fire) ─

    def _set_silently(self, box: QComboBox, text: str) -> None:
        box.blockSignals(True)
        box.setCurrentText(text)
        box.blockSignals(False)

    def sync_monitor_combo(self, key: str) -> None:
        self._set_silently(self._monitors, key)

    def sync_thermal_combo(self, key: str) -> None:
        self._set_silently(self._thermal, key)

    def sync_animate(self, on: bool) -> None:
        self._animate.blockSignals(True)
        self._animate.setChecked(on)
        self._animate.blockSignals(False)


# ── Smoke test (used by --smoke; safe to run offscreen) ─────────────────────


def _smoke_report(driver: MockDriver, name: str) -> None:
    d = driver.dashboard
    print(
        f"[smoke] {name!r}: "
        f"cpu={d._cards['cpu_usage']._value.text()!r} "
        f"monitor={d._monitor_card_slot.isVisibleTo(d)} "
        f"empty={d._monitor_empty_slot.isVisibleTo(d)} "
        f"extras={len(d._monitor_cards)} "
        f"nvidia_full={d._nvidia_full_card.isVisibleTo(d)} "
        f"nvidia_dlss={d._nvidia_dlss_card.isVisibleTo(d)} "
        f"chart_offline={d.thermal_chart._offline} "
        f"mouse={d._mouse_poll_card._poll_status.text()!r}"
    )


def _run_smoke(app: QApplication, driver: MockDriver) -> None:
    names = list(fx.SCENARIOS)

    def step(i: int) -> None:
        if i >= len(names):
            driver.apply_monitors("multi")  # exercises the dynamic-extras path
            _smoke_report(driver, "multi-monitor")
            driver.set_animation(False)
            print("[smoke] OK")
            app.quit()
            return
        driver.apply_scenario(names[i])
        _smoke_report(driver, names[i])
        QTimer.singleShot(250, lambda: step(i + 1))

    QTimer.singleShot(0, lambda: step(0))


# ── Entry ───────────────────────────────────────────────────────────────────


def main() -> int:
    smoke = "--smoke" in sys.argv

    QApplication.setApplicationName("lil_bro")
    QApplication.setOrganizationName("lil_bro")
    app = QApplication(sys.argv)

    theme.load_fonts()
    app.setStyleSheet(theme.build_stylesheet())

    main_win = MainWindow(settings=None)
    main_win.status_bar_widget.set_session("mock")
    main_win.status_bar_widget.set_model("Mock Fixtures")
    main_win.status_bar_widget.set_state("ok", "MOCK MODE — no system access")

    apply_monkeypatches()
    driver = MockDriver(main_win)
    panel = MockControls(driver)

    main_win.show()  # before set_monitor_data — mirrors app.py ordering

    if smoke:
        _run_smoke(app, driver)
        return app.exec()

    panel._set_silently(panel._scenario, "Mixed issues")
    panel._on_apply_scenario()
    panel.move(main_win.frameGeometry().topRight() + QPoint(12, 0))
    panel.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
