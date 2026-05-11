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


class ConfirmDialog(QDialog):
    def __init__(self, question: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm")
        self.setModal(True)
        self.setAccessibleName("Confirm dialog")
        self.setAccessibleDescription(question)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        prompt = QLabel(question)
        prompt.setWordWrap(True)
        layout.addWidget(prompt)

        buttons = QDialogButtonBox(self)
        self.yes_btn: QPushButton = buttons.addButton(
            "Yes", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.no_btn: QPushButton = buttons.addButton(
            "No", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.yes_btn.setObjectName("primary")
        self.yes_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
