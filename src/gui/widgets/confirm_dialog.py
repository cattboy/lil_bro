"""Modal Yes/No dialog for ``prompt_confirm`` calls (model download, soft confirms).

Behavior contract: Yes → True, No / Esc / close → False.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsDropShadowEffect,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


from PySide6.QtWidgets import QHBoxLayout  # noqa: E402

class ConfirmDialog(QDialog):
    """V2 confirm dialog: ⚡ accent icon, restore-point context, Yes/Skip buttons."""

    def __init__(self, title: str, description: str = "", parent=None,
                 yes_label: str = "Yes, Continue", no_label: str = "Skip") -> None:
        super().__init__(parent)
        # objectName drives the elevated "card" styling (surface bg + border +
        # 12px radius) shared with the batch dialog -- see _qss_confirm_dialog.
        self.setObjectName("confirmDialog")
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

        self.no_btn = QPushButton(f"{no_label} (S)")
        self.no_btn.setObjectName("secondary")
        # Secondary button must not auto-default: otherwise, when it takes the
        # dialog's initial focus, the WASD filter's W (= click the default
        # button) can fire reject() instead of accept(). See the project's
        # autoDefault/WASD dialog rule.
        self.no_btn.setAutoDefault(False)
        self.no_btn.clicked.connect(self.reject)

        self.yes_btn = QPushButton(f"{yes_label} (W)")
        self.yes_btn.setObjectName("primary")
        self.yes_btn.setDefault(True)
        self.yes_btn.clicked.connect(self.accept)
        # Accent glow makes the W/accept button the clear focal point, per
        # DESIGN.md's "primary accent elements get a soft glow" (QSS can't do
        # box-shadow, so we use a drop-shadow effect with the accent colour).
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(24)
        glow.setColor(QColor(0, 229, 204, 150))  # accent #00E5CC, soft alpha
        glow.setOffset(0, 0)
        self.yes_btn.setGraphicsEffect(glow)

        btn_row.addWidget(self.no_btn)
        btn_row.addWidget(self.yes_btn)
        layout.addLayout(btn_row)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)
