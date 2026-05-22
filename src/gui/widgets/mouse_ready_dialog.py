"""Modal confirmation dialog shown before mouse polling measurement in the pipeline.

Blocks the pipeline worker thread until the user clicks OK. Esc also accepts —
there is no meaningful skip because the pipeline always runs the measurement.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class MouseReadyDialog(QDialog):
    """Single-action dialog that prompts the user to start moving their mouse."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Mouse Polling Check")
        self.setModal(True)
        self.setFixedWidth(420)
        self.setAccessibleName("Mouse ready dialog")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        accent_bar = QFrame()
        accent_bar.setObjectName("mouseReadyAccent")
        accent_bar.setFixedHeight(2)
        layout.addWidget(accent_bar)

        title_lbl = QLabel("Mouse Polling Check")
        title_lbl.setObjectName("mouseReadyTitle")
        title_lbl.setWordWrap(True)
        layout.addWidget(title_lbl)

        desc_lbl = QLabel(
            "We need 2 seconds of mouse movement to measure your polling rate.\n\n"
            "Click the button below and start wiggling your mouse — "
            "the measurement begins immediately."
        )
        desc_lbl.setObjectName("mouseReadyDesc")
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        ok_btn = QPushButton("OK — Start Moving Mouse")
        ok_btn.setObjectName("primary")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)
