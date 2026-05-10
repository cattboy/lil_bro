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
from PySide6.QtGui import QAction, QDesktopServices
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


_PHASE_NAMES = (
    "1. Bootstrap",
    "2. Scan",
    "3. Baseline",
    "4. Configure",
    "5. Verify",
)


class MainWindow(QMainWindow):
    """The lil_bro GUI shell."""

    DASHBOARD_INDEX = 0
    OUTPUT_INDEX = 1

    def __init__(self, parent: QWidget | None = None,
                 settings: Settings | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("lil_bro")
        self.setMinimumSize(1024, 720)
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

        self._build_menu()

        status = QStatusBar(self)
        status.showMessage(_status_text())
        self.setStatusBar(status)

    # ── Sidebar ────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        from src.gui.widgets.thermal_chart import ThermalChart

        frame = QFrame()
        frame.setObjectName("sidebar")
        frame.setFixedWidth(280)
        frame.setAccessibleName("Sidebar")

        col = QVBoxLayout(frame)
        col.setContentsMargins(24, 24, 24, 24)
        col.setSpacing(16)

        header = QLabel("Optimization")
        header.setObjectName("sectionHeader")
        col.addWidget(header)

        for name in _PHASE_NAMES:
            card = QLabel(name)
            card.setObjectName("phaseCard")
            card.setFrameShape(QLabel.Shape.StyledPanel)
            card.setProperty("phaseStatus", "pending")
            card.setAccessibleName(f"Phase: {name}")
            col.addWidget(card)

        col.addStretch(1)

        # Live CPU + GPU thermal chart. Starts in offline mode; ``app.run()``
        # flips it to live samples once the LHM sidecar reports ready.
        self.thermal_chart = ThermalChart()
        self.thermal_chart.set_offline("Thermal monitor not started")
        col.addWidget(self.thermal_chart)
        return frame

    # ── Content ────────────────────────────────────────────────────────

    def _build_content(self) -> QStackedWidget:
        stack = QStackedWidget()
        stack.setAccessibleName("Content area")

        # Dashboard placeholder (filled in Step 10).
        dashboard = QWidget()
        dashboard.setObjectName("dashboardView")
        dlayout = QVBoxLayout(dashboard)
        dlayout.setContentsMargins(48, 48, 48, 48)
        dlayout.setSpacing(24)

        title = QLabel("Run Optimization")
        title.setObjectName("sectionHeader")
        dlayout.addWidget(title)

        self._run_button = QPushButton("Run Optimization")
        self._run_button.setObjectName("primary")
        self._run_button.setMinimumHeight(48)
        self._run_button.setAccessibleName("Run optimization pipeline")
        dlayout.addWidget(self._run_button, alignment=Qt.AlignmentFlag.AlignLeft)

        dlayout.addStretch(1)
        stack.addWidget(dashboard)

        # Output panel placeholder (filled in Step 6).
        output = QLabel("Output panel placeholder — pipeline log streams here.")
        output.setObjectName("outputPanelPlaceholder")
        output.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        output.setAccessibleName("Pipeline output panel")
        stack.addWidget(output)

        stack.setCurrentIndex(self.DASHBOARD_INDEX)
        return stack

    # ── Menu ───────────────────────────────────────────────────────────

    def _build_menu(self) -> None:
        bar = self.menuBar()
        file_menu = bar.addMenu("&File")

        self.action_run_pipeline = QAction("Run &Optimization", self)
        self.action_ai_setup = QAction("&AI Setup", self)
        self.action_revert = QAction("&Revert last session", self)
        self.action_exit = QAction("E&xit", self)
        self.action_exit.triggered.connect(self.close)

        file_menu.addAction(self.action_run_pipeline)
        file_menu.addAction(self.action_ai_setup)
        file_menu.addAction(self.action_revert)
        file_menu.addSeparator()
        file_menu.addAction(self.action_exit)

        help_menu = bar.addMenu("&Help")
        action_open_log = QAction("Open Debug Log", self)
        action_open_log.triggered.connect(self._open_debug_log)
        help_menu.addAction(action_open_log)

    # ── View toggle ────────────────────────────────────────────────────

    def show_dashboard(self) -> None:
        self._content.setCurrentIndex(self.DASHBOARD_INDEX)

    def show_output(self) -> None:
        self._content.setCurrentIndex(self.OUTPUT_INDEX)

    def _open_debug_log(self) -> None:
        from src.utils.paths import get_debug_log_path
        path = get_debug_log_path()
        if path.exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
        else:
            QMessageBox.information(
                self,
                "Debug Log",
                "No debug log found.\n\nRun lil_bro at least once (GUI mode always writes a log).",
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
