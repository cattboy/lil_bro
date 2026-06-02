"""Modal Approve/Deny dialog used for ``prompt_approval`` calls.

Behavior contract:
- Approve → exec returns ``QDialog.DialogCode.Accepted`` (truthy bool)
- Deny / Esc / window close → ``Rejected`` (falsy)
- Approve is the focused default button; Esc maps to Deny per Qt convention
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


class ApprovalDialog(QDialog):
    def __init__(self, action: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Requires Approval")
        self.setModal(True)
        self.setAccessibleName("Approval dialog")
        self.setAccessibleDescription(action)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        prompt = QLabel(action)
        prompt.setWordWrap(True)
        prompt.setObjectName("dialogPrompt")
        layout.addWidget(prompt)

        buttons = QDialogButtonBox(self)
        self.approve_btn: QPushButton = buttons.addButton(
            "Approve (W)", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.deny_btn: QPushButton = buttons.addButton(
            "Deny (S)", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.approve_btn.setObjectName("primary")
        self.approve_btn.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def keyPressEvent(self, event):  # noqa: D401  Qt override
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
