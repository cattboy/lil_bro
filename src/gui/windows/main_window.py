"""QMainWindow: sidebar + content area + status bar.

The sidebar holds 5 phase cards + a thermal chart slot + menu actions.
The content area toggles between the dashboard (home) and the output
panel (during pipeline runs).

Step 5 lays the structural shell. Phase cards (Step 6), the output
panel (Step 6), the dashboard (Step 10), and the thermal chart (Step
10) replace the placeholder labels in subsequent commits.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.gui.settings import Settings


from PySide6.QtWidgets import QProgressBar

_PHASE_NAMES = (
    "1. Bootstrap",
    "2. Scan",
    "3. Baseline",
    "4. Configure",
    "5. Verify",
)


class MainWindow(QMainWindow):
    """The lil_bro GUI shell — V2 layout."""

    DASHBOARD_INDEX = 0
    OUTPUT_INDEX = 1

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
        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(220)
        frame.setAccessibleName("Sidebar navigation")

        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 20, 0, 16)
        col.setSpacing(2)

        # Brand
        brand = QLabel("lil_bro")
        brand.setObjectName("sidebarBrand")
        col.addWidget(brand)

        # Primary nav
        self._run_button = self._nav_btn("▶  Start Optimization", accent=True)
        self._nav_dashboard = self._nav_btn("◆  Dashboard")
        col.addWidget(self._nav_dashboard)
        col.addWidget(self._run_button)

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
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    # ── Content ────────────────────────────────────────────────────────

    def _build_content(self) -> QStackedWidget:
        from src.gui.widgets.dashboard import Dashboard
        from src.gui.widgets.output_panel import OutputPanel
        from src.gui.widgets.benchmark_row import BenchmarkRow

        stack = QStackedWidget()
        stack.setAccessibleName("Content area")

        # ── Dashboard view ───────────────────────────────────────────
        self._dashboard = Dashboard()
        stack.addWidget(self._dashboard)

        # ── Output / Pipeline view ───────────────────────────────────
        output_page = QWidget()
        output_page.setObjectName("outputView")
        output_layout = QVBoxLayout(output_page)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(0)

        # Header row
        output_header = QFrame()
        output_header.setObjectName("outputHeader")
        hdr_row = QHBoxLayout(output_header)
        hdr_row.setContentsMargins(20, 12, 20, 12)

        self._output_title = QLabel("Pipeline")
        self._output_title.setObjectName("outputTitle")
        hdr_row.addWidget(self._output_title)
        hdr_row.addStretch()

        self._phase_pill = QLabel("○ Idle")
        self._phase_pill.setObjectName("sbLabel")
        hdr_row.addWidget(self._phase_pill)

        output_layout.addWidget(output_header)

        # Benchmark score row
        self._benchmark_row = BenchmarkRow()
        output_layout.addWidget(self._benchmark_row)

        # Progress bar (hidden until pipeline emits progress_changed)
        self._progress_label = QLabel("")
        self._progress_label.setObjectName("progressLabel")
        self._progress_label.setVisible(False)
        self._progress_label.setContentsMargins(20, 4, 20, 0)
        output_layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 100)
        self._progress_bar.setValue(0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedHeight(4)
        self._progress_bar.setAccessibleName("Pipeline progress")
        self._progress_bar.setVisible(False)
        self._progress_bar.setContentsMargins(20, 0, 20, 0)
        output_layout.addWidget(self._progress_bar)

        # Output panel with toolbar
        self._output_panel = OutputPanel()
        output_layout.addWidget(self._output_panel, stretch=1)

        stack.addWidget(output_page)
        stack.setCurrentIndex(self.DASHBOARD_INDEX)
        return stack

    # ── View toggle ────────────────────────────────────────────────────

    def show_dashboard(self) -> None:
        self._content.setCurrentIndex(self.DASHBOARD_INDEX)
        self._set_nav_active(self._nav_dashboard)

    def show_output(self) -> None:
        self._content.setCurrentIndex(self.OUTPUT_INDEX)
        self._set_nav_active(self._run_button)

    # ── Phase row proxy (wired by app.py via phase_changed signal) ─────

    def update_benchmark_score(self, phase: str, scores: dict, cpu_peak: float | None) -> None:
        if phase == "baseline":
            self._benchmark_row.set_baseline(scores, cpu_peak)
            self._phase_pill.setText("● Benchmark")
        elif phase == "final":
            self._benchmark_row.set_final(scores)
            self._phase_pill.setText("✓ Complete")

    # ── Nav "working" indicator for Run button ─────────────────────────

    def set_running(self, running: bool) -> None:
        """Toggle the Run nav button between normal and 'working' states."""
        if running:
            self._run_button.setText("▣  Working…")
            self._run_button.setProperty("navState", "active")
        else:
            self._run_button.setText("▶  Start Optimization")
            self._run_button.setProperty("navState", "")
        self._run_button.style().unpolish(self._run_button)
        self._run_button.style().polish(self._run_button)

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


def _status_text() -> str:
    try:
        from src._version import __version__ as version
    except Exception:
        version = "?"
    return f"lil_bro v{version}  ·  ready"
