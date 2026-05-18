"""Modal Yes/No dialog for ``prompt_confirm`` calls (model download, soft confirms).

Behavior contract: Yes → True, No / Esc / close → False.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


from PySide6.QtWidgets import QHBoxLayout  # noqa: E402

class ConfirmDialog(QDialog):
    """V2 confirm dialog: ⚡ accent icon, restore-point context, Yes/Skip buttons."""

    def __init__(self, title: str, description: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedWidth(420)
        self.setAccessibleName("Confirm dialog")
        self.setAccessibleDescription(description or title)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        # ── Icon + text row ──────────────────────────────────────────
        body_row = QHBoxLayout()
        body_row.setSpacing(14)
        body_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon = QLabel("⚡")
        icon.setObjectName("confirmIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        body_row.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("confirmTitle")
        title_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)

        self._desc_lbl = QLabel(description)
        self._desc_lbl.setObjectName("confirmDesc")
        self._desc_lbl.setWordWrap(True)
        if not description:
            self._desc_lbl.hide()
        text_col.addWidget(self._desc_lbl)

        body_row.addLayout(text_col)
        layout.addLayout(body_row)

        # ── Buttons ──────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.no_btn = QPushButton("Skip")
        self.no_btn.setObjectName("secondary")
        self.no_btn.clicked.connect(self.reject)

        self.yes_btn = QPushButton("Yes, Continue")
        self.yes_btn.setObjectName("primary")
        self.yes_btn.setDefault(True)
        self.yes_btn.clicked.connect(self.accept)

        btn_row.addWidget(self.no_btn)
        btn_row.addWidget(self.yes_btn)
        layout.addLayout(btn_row)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
