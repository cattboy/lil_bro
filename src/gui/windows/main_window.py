"""QMainWindow: sidebar + content area + status bar.

The sidebar holds 5 phase cards + a thermal chart slot + menu actions.
The content area toggles between the dashboard (home) and the output
panel (during pipeline runs).

Step 5 lays the structural shell. Phase cards (Step 6), the output
panel (Step 6), the dashboard (Step 10), and the thermal chart (Step
10) replace the placeholder labels in subsequent commits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from src.gui.theme import repolish

if TYPE_CHECKING:
    from src.gui.settings import Settings


class MainWindow(QMainWindow):
    """The lil_bro GUI shell — V2 layout."""

    DASHBOARD_INDEX = 0
    OUTPUT_INDEX = 1

    # Emitted when the user requests cancellation of the running pipeline.
    # Connected to PipelineWorker.request_cancel in app.py. Fires from the
    # Stop button, the Esc/Q hotkeys (when pipeline is running), or
    # programmatic _on_stop_clicked() calls when the button is visible.
    stop_requested = Signal()

    def __init__(self, parent: QWidget | None = None,
                 settings: Settings | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("lil_bro")
        self.setMinimumSize(1280, 800)
        self.setAccessibleName("lil_bro main window")
        self.setAccessibleDescription("Local AI gaming PC optimizer")

        self._settings = settings
        if self._settings is not None:
            self._settings.restore_geometry(self)

        self._sidebar = self._build_sidebar()
        self._content = self._build_content()

        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._content, stretch=1)
        self.setCentralWidget(root)

        self.menuBar().hide()

        # Hide the default Qt status bar and use our custom widget instead
        self.statusBar().hide()

        from src.gui.widgets.status_bar_widget import StatusBarWidget
        self.status_bar_widget = StatusBarWidget()
        self._inject_status_bar(self.status_bar_widget)

        # Cancel hotkeys: Esc, Q, Return (main Enter), Enter (numpad).
        # Q + Return mirror the CLI's b"q"/b"Q"/b"\r" mapping in
        # _keyboard_abort_watcher; Esc is added because dialogs already
        # bind it to dismiss; Key_Enter is the numpad Enter, distinct from
        # Key_Return on Qt. Qt.WindowShortcut (the default) fires only when
        # MainWindow is the active window -- NOT when a modal ApprovalDialog
        # has focus -- so dialog Esc/Enter handlers stay intact.
        # _on_stop_clicked gates on _stop_button.isVisible(), so all four
        # keys are no-ops while the pipeline is idle.
        self._stop_shortcuts = []
        for key in (
            Qt.Key.Key_Escape,
            Qt.Key.Key_Q,
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(self._on_stop_clicked)
            self._stop_shortcuts.append(shortcut)

    def _inject_status_bar(self, widget) -> None:
        """Pin the custom status bar widget to the bottom of the main window."""
        from PySide6.QtWidgets import QVBoxLayout
        central = self.centralWidget()
        outer = QWidget()
        vbox = QVBoxLayout(outer)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)
        vbox.addWidget(central)
        vbox.addWidget(widget)
        self.setCentralWidget(outer)

    # ── Sidebar ────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        from src.gui.theme import COLORS

        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(220)
        frame.setAccessibleName("Sidebar navigation")

        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 20, 0, 16)
        col.setSpacing(2)

        # Brand — "lil" stays primary text, "_bro" gets the accent cyan.
        # One rich-text label keeps letter-spacing uniform across the wordmark.
        brand = QLabel(f'lil<span style="color: {COLORS["accent"]};">_bro</span>')
        brand.setObjectName("sidebarBrand")
        brand.setTextFormat(Qt.TextFormat.RichText)
        col.addWidget(brand)

        # Primary nav
        self._run_button = self._nav_btn("▶  Start Optimization", accent=True)
        self._stop_button = self._nav_btn("■  Stop (Esc)", state="danger")
        self._stop_button.setVisible(False)
        self._nav_dashboard = self._nav_btn("◆  Dashboard")
        col.addWidget(self._nav_dashboard)
        col.addWidget(self._run_button)
        col.addWidget(self._stop_button)

        col.addStretch(1)

        # Divider
        divider = QFrame()
        divider.setObjectName("navDivider")
        divider.setFixedHeight(1)
        col.addWidget(divider)
        col.addSpacing(4)

        # Utility nav
        self._nav_log = self._nav_btn("📄  View Debug Log", state="muted")
        self._revert_button = self._nav_btn("↩  Revert Changes", state="warning")
        self._ai_setup_button = self._nav_btn("⚙  AI Setup", state="muted")
        self._nav_exit = self._nav_btn("✕  Exit", state="danger")

        col.addWidget(self._nav_log)
        col.addWidget(self._revert_button)
        col.addWidget(self._ai_setup_button)
        col.addWidget(self._nav_exit)

        # Wire built-in nav actions
        self._nav_dashboard.clicked.connect(self.show_dashboard)
        self._run_button.clicked.connect(self.show_output)
        self._stop_button.clicked.connect(self._on_stop_clicked)
        self._nav_log.clicked.connect(self._open_debug_log)
        self._nav_exit.clicked.connect(self.close)

        # Default active state
        self._set_nav_active(self._nav_dashboard)

        return frame

    def _nav_btn(self, label: str, accent: bool = False,
                 state: str = "") -> QPushButton:
        btn = QPushButton(label)
        btn.setProperty("navRole", "nav")
        btn.setProperty("navState", state if state else ("active" if accent else ""))
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFlat(True)
        btn.setMinimumHeight(36)
        return btn

    def _set_nav_active(self, active_btn: QPushButton) -> None:
        for btn in (self._nav_dashboard, self._run_button):
            state = "active" if btn is active_btn else ""
            btn.setProperty("navState", state)
            repolish(btn)

    # ── Content ────────────────────────────────────────────────────────

    def _build_content(self) -> QStackedWidget:
        from src.gui.widgets.dashboard import Dashboard
        from src.gui.widgets.output_view import OutputView

        stack = QStackedWidget()
        stack.setAccessibleName("Content area")

        # ── Dashboard view ───────────────────────────────────────────
        self._dashboard = Dashboard()
        stack.addWidget(self._dashboard)

        # ── Output / Pipeline view ───────────────────────────────────
        self._output_view = OutputView()
        # Re-export the sub-widgets app.py and update_benchmark_score drive,
        # so external access (main._benchmark_row, main._output_panel, …)
        # stays unchanged after the OutputView extraction.
        self._output_title = self._output_view._output_title
        self._phase_pill = self._output_view._phase_pill
        self._live_stat_row = self._output_view._live_stat_row
        self._benchmark_row = self._output_view._benchmark_row
        self._progress_label = self._output_view._progress_label
        self._progress_bar = self._output_view._progress_bar
        self._output_panel = self._output_view._output_panel
        stack.addWidget(self._output_view)

        stack.setCurrentIndex(self.DASHBOARD_INDEX)
        return stack

    # ── View toggle ────────────────────────────────────────────────────

    def show_dashboard(self) -> None:
        self._content.setCurrentIndex(self.DASHBOARD_INDEX)
        self._set_nav_active(self._nav_dashboard)

    def show_output(self) -> None:
        self._content.setCurrentIndex(self.OUTPUT_INDEX)
        self._set_nav_active(self._run_button)

    # ── Benchmark score proxy (wired by app.py via benchmark_score_ready) ──

    def update_benchmark_score(self, phase: str, scores: dict, cpu_peak: float | None) -> None:
        if phase == "baseline":
            self._benchmark_row.set_baseline(scores, cpu_peak)
            self._phase_pill.setText("● Benchmark")
        elif phase == "final":
            self._benchmark_row.set_final(scores)
            self._phase_pill.setText("✓ Complete")

    # ── Nav "working" indicator for Run button ─────────────────────────

    def set_running(self, running: bool) -> None:
        """Toggle the Run nav button between normal and 'working' states.

        Also flips the Stop button's visibility so the cancel control only
        appears while a pipeline run is in progress.
        """
        if running:
            self._run_button.setText("▣  Working…")
            self._run_button.setProperty("navState", "active")
        else:
            self._run_button.setText("▶  Start Optimization")
            self._run_button.setProperty("navState", "")
        repolish(self._run_button)
        self._stop_button.setVisible(running)

    def _on_stop_clicked(self) -> None:
        """Emit ``stop_requested`` only while the pipeline is running.

        The Stop button is hidden during idle, but Esc/Q QShortcuts fire
        regardless of button visibility. Gating on ``_stop_button.isVisible()``
        keeps the hotkeys silent when no pipeline is running, so users don't
        get phantom cancel events while idle.
        """
        if self._stop_button.isVisible():
            self.stop_requested.emit()

    # ── Debug log ──────────────────────────────────────────────────────

    def _open_debug_log(self) -> None:
        from src.utils.paths import get_debug_log_path
        path = get_debug_log_path()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "Debug Log",
                "No debug log found.\n\nRun lil_bro at least once to generate a log.",
            )

    # ── Lifecycle ──────────────────────────────────────────────────────

    def closeEvent(self, event):  # noqa: N802  Qt override
        if self._settings is not None:
            self._settings.save_geometry(self)
        super().closeEvent(event)
