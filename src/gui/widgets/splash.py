"""QSplashScreen for the 3-9 sec cold-start gap.

The brand mark + status updates close the trust gap that would otherwise
burn first-run users on an admin-elevated tool. Per Design Review the
brand voice tagline lives here ("the friend who knows computers") while
the step status messages stay utility ("Initializing UI…", "Starting
thermal monitor…", "Ready.").
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QSplashScreen


_SPLASH_W = 480
_SPLASH_H = 320


def make_splash() -> QSplashScreen:
    """Return a styled splash screen ready for ``show()``."""
    pixmap = QPixmap(_SPLASH_W, _SPLASH_H)
    pixmap.fill(QColor("#2E2F3A"))  # elevated

    painter = QPainter(pixmap)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Brand mark — JetBrains Mono Bold in accent cyan.
        brand_font = QFont("JetBrains Mono", 36, QFont.Weight.Bold)
        painter.setFont(brand_font)
        painter.setPen(QColor("#00E5CC"))
        painter.drawText(
            pixmap.rect().adjusted(0, -32, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "lil_bro",
        )

        # Tagline — DM Sans, secondary text color (brand voice).
        tagline_font = QFont("DM Sans", 11)
        painter.setFont(tagline_font)
        painter.setPen(QColor("#9B9AA0"))
        painter.drawText(
            pixmap.rect().adjusted(0, 80, 0, 0),
            Qt.AlignmentFlag.AlignCenter,
            "the friend who knows computers",
        )
    finally:
        painter.end()

    splash = QSplashScreen(pixmap, Qt.WindowType.WindowStaysOnTopHint)
    splash.setObjectName("splash")
    update_splash(splash, "Loading…")
    return splash


def update_splash(splash: QSplashScreen, message: str) -> None:
    """Show a status update along the splash bottom."""
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#9B9AA0"),
    )


def show_splash_error(splash: QSplashScreen, message: str) -> None:
    """Render an error-state status (coral) when a startup step fails."""
    splash.showMessage(
        message,
        Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter,
        QColor("#FF6B6B"),
    )


from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_STEP_NAMES = ("LHM Monitor", "Sensors")


class SplashDialog(QDialog):
    """V2 full-screen splash: brand + tagline + 3 auto-advancing init steps."""

    def __init__(self, parent=None) -> None:
        from PySide6.QtWidgets import QProgressBar
        super().__init__(parent)
        self.setObjectName("splashDialog")
        self.setWindowTitle("lil_bro")
        self.setModal(True)
        self.setFixedSize(560, 340)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)

        self._step_states: list[str] = ["pending"] * len(_STEP_NAMES)
        self._step_done_count = 0

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(48, 40, 48, 40)
        vbox.setSpacing(0)
        vbox.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # Brand
        brand_row = QHBoxLayout()
        brand_row.setSpacing(0)
        brand_lbl = QLabel("lil")
        brand_lbl.setObjectName("splashBrand")
        brand_accent = QLabel("_bro")
        brand_accent.setObjectName("splashBrandAccent")
        brand_row.addStretch()
        brand_row.addWidget(brand_lbl)
        brand_row.addWidget(brand_accent)
        brand_row.addStretch()
        vbox.addLayout(brand_row)
        vbox.addSpacing(12)

        tagline = QLabel("Your Local AI PC\nOptimization Agent")
        tagline.setObjectName("splashTagline")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(tagline)
        vbox.addSpacing(12)

        badge = QLabel("100% Offline  ·  Privacy First")
        badge.setObjectName("splashBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vbox.addWidget(badge)
        vbox.addStretch(1)

        # Step rows
        steps_frame = QFrame()
        steps_col = QVBoxLayout(steps_frame)
        steps_col.setContentsMargins(0, 0, 0, 0)
        steps_col.setSpacing(8)

        self._step_icons: list[QLabel] = []
        self._step_results: list[QLabel] = []
        for name in _STEP_NAMES:
            row = QHBoxLayout()
            row.setSpacing(10)

            icon = QLabel("○")
            icon.setObjectName("splashStepIcon")
            icon.setProperty("stepState", "pending")
            icon.setFixedWidth(16)
            self._step_icons.append(icon)

            label = QLabel(name)
            label.setObjectName("splashStepLabel")

            result = QLabel("")
            result.setObjectName("splashStepResult")
            result.setProperty("stepState", "pending")
            result.setFixedWidth(28)
            result.setAlignment(Qt.AlignmentFlag.AlignRight)
            self._step_results.append(result)

            row.addWidget(icon)
            row.addWidget(label, stretch=1)
            row.addWidget(result)
            steps_col.addLayout(row)

        vbox.addWidget(steps_frame)
        vbox.addSpacing(16)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setObjectName("splashProgress")
        self._progress.setRange(0, len(_STEP_NAMES))
        self._progress.setValue(0)
        self._progress.setTextVisible(False)
        self._progress.setFixedHeight(4)
        vbox.addWidget(self._progress)

        # Pre-set step 0 as running so it shows active before first signal arrives
        self._set_step_state(0, "run")

    def _set_step_state(self, idx: int, state: str) -> None:
        icons = {"pending": "○", "run": "●", "done": "✓"}
        results = {"pending": "", "run": "…", "done": "OK"}
        icon = self._step_icons[idx]
        result = self._step_results[idx]
        icon.setText(icons.get(state, "○"))
        icon.setProperty("stepState", state)
        icon.style().unpolish(icon)
        icon.style().polish(icon)
        result.setText(results.get(state, ""))
        result.setProperty("stepState", state)
        result.style().unpolish(result)
        result.style().polish(result)

    def on_init_step(self, name: str, status: str) -> None:
        """Slot wired to StartupOrchestrator.init_step signal."""
        try:
            idx = list(_STEP_NAMES).index(name)
        except ValueError:
            return  # unknown step name — ignore
        if status == "running":
            self._set_step_state(idx, "run")
        elif status in ("done", "fail"):
            self._set_step_state(idx, "done")
            self._step_done_count += 1
            self._progress.setValue(self._step_done_count)
            if idx + 1 < len(_STEP_NAMES):
                self._set_step_state(idx + 1, "run")
            if self._step_done_count >= len(_STEP_NAMES):
                QTimer.singleShot(600, self.accept)
