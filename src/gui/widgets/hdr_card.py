"""Dashboard card for HDR optimization (detection-only v1).

Shows the best HDR path for the user's hardware (RTX HDR > Auto HDR > base HDR)
and deep-links to the native UI to turn it on. NO system writes in v1 — the
one-click Auto HDR / RTX HDR writes are TODOS T-039 / T-040.

States (from ``analyze_hdr``):
  optimal      → "✓ ... is on", no button, sev=low
  suboptimal   → recommendation + deep-link button, sev=medium
  hdr_off      → "turn on HDR" + Windows settings deep-link, sev=medium
The dashboard hides the card entirely when HDR capability is undetermined or no
HDR panel exists (see ``hdr_card_visible`` in ``agent_tools/hdr.py``).

Layout mirrors ``MonitorRefreshCard`` (object names reuse the pollWidget QSS).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from src.agent_tools.hdr import HDR_SETTINGS_URI, NVIDIA_APP_LINK, hdr_priority_hint_lines
from src.gui.theme import repolish


def _open_nvidia_app() -> None:
    """Best-effort launch of the NVIDIA app; falls back to Windows HDR settings.

    There is no stable URI for the NVIDIA app, so we try common install paths and
    degrade to ``ms-settings:display`` (HDR must be enabled in Windows anyway) so
    the button is never a dead end.
    """
    import os

    candidates = [
        os.path.expandvars(r"%ProgramFiles%\NVIDIA Corporation\NVIDIA App\CEF\NVIDIA App.exe"),
        os.path.expandvars(r"%ProgramFiles%\NVIDIA Corporation\NVIDIA App\NVIDIA App.exe"),
    ]
    for path in candidates:
        # QDesktopServices (ShellExecute) launches the GUI app with no console
        # window; os.startfile is banned by the no-console-window guard.
        if os.path.isfile(path) and QDesktopServices.openUrl(QUrl.fromLocalFile(path)):
            return
    QDesktopServices.openUrl(QUrl(HDR_SETTINGS_URI))


class HDRCard(QFrame):
    """Detection-only HDR card. ``set_hdr_status(finding)`` populates it."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("hdrCard")
        self.setAccessibleName("HDR optimization card")
        # Pin to sizeHint — never let a squeezed parent compress the card
        # (same rule as MonitorRefreshCard).
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        self._deep_link: str | None = None

        root = QHBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        left = QVBoxLayout()
        left.setSpacing(4)

        # Title row: "HDR" + a "?" InfoMarker whose flyout shows the priority
        # ladder (rendered from the shared HDR_PRIORITY constant so the hint can
        # never disagree with the analyzer's recommendation).
        title_row = QHBoxLayout()
        title_row.setSpacing(6)
        self._title_lbl = QLabel("HDR")
        self._title_lbl.setObjectName("pollLabel")
        title_row.addWidget(self._title_lbl)

        # InfoMarker imported lazily — keeps this widget importable in headless
        # contexts where the coachmarks tooltip helper isn't needed at import time.
        from src.gui.widgets.info_marker import InfoMarker

        hint_body = "Best HDR path for your PC, in order:<br>" + "<br>".join(
            hdr_priority_hint_lines()
        ) + "<br><br>lil_bro picks the right one for your hardware."
        self._hint = InfoMarker("HDR makes games brighter and more vivid", hint_body)
        title_row.addWidget(self._hint)
        title_row.addStretch()
        left.addLayout(title_row)

        self._status_lbl = QLabel("")
        self._status_lbl.setObjectName("pollStatus")
        self._status_lbl.setWordWrap(True)
        left.addWidget(self._status_lbl)

        root.addLayout(left, 1)

        self._action_btn = QPushButton("Open HDR settings")
        self._action_btn.setObjectName("secondary")
        self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._action_btn.setFixedWidth(160)
        self._action_btn.setVisible(False)
        self._action_btn.clicked.connect(self._on_action_clicked)
        root.addWidget(self._action_btn, alignment=Qt.AlignmentFlag.AlignVCenter)

    def set_hdr_status(self, finding: dict) -> None:
        """Populate the card from an ``analyze_hdr`` finding."""
        state = finding.get("state")
        msg = finding.get("message", "")
        if finding.get("fps_note"):
            msg += " (RTX HDR costs a few FPS on this card.)"
        self._status_lbl.setText(msg)
        self._deep_link = finding.get("deep_link")

        if state in ("suboptimal", "hdr_off"):
            self._status_lbl.setProperty("sev", "medium")
            self._action_btn.setText(
                "Open NVIDIA App" if self._deep_link == NVIDIA_APP_LINK else "Open HDR settings"
            )
            self._action_btn.setVisible(bool(self._deep_link))
        else:  # optimal / not_applicable / hidden
            self._status_lbl.setProperty("sev", "low")
            self._action_btn.setVisible(False)

        repolish(self._status_lbl)

    def _on_action_clicked(self) -> None:
        if self._deep_link == NVIDIA_APP_LINK:
            _open_nvidia_app()
        elif self._deep_link:
            QDesktopServices.openUrl(QUrl(self._deep_link))
