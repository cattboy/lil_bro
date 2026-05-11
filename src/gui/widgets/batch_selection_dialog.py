"""Multi-select dialog mirroring CLI ``run_approval_flow`` batch input.

CLI parses ``"1 3"`` / ``"all"`` / ``"skip"``. The GUI replaces that
single-line prompt with a checkable list + three actions:

- Apply selected → return the list of selected 1-based indices
- Apply all → return ``[1..n]``
- Skip / Esc → return ``[]``
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)


class BatchSelectionDialog(QDialog):
    def __init__(self, proposals: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply Optimizations")
        self.setModal(True)
        self.setAccessibleName("Batch selection dialog")

        self._proposals = proposals
        self._selected_indices: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        header = QLabel("Choose optimizations to apply")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        for i, proposal in enumerate(proposals, start=1):
            title = proposal.get("title") or proposal.get("finding") or f"Proposal {i}"
            severity = proposal.get("severity", "")
            label = f"[{i}] {severity}  {title}".strip()
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = bool(proposal.get("can_auto_fix", True))
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self._list.addItem(item)
        layout.addWidget(self._list, stretch=1)

        actions = QHBoxLayout()
        self.apply_all_btn = QPushButton("Apply all")
        self.skip_btn = QPushButton("Skip all")
        actions.addWidget(self.apply_all_btn)
        actions.addWidget(self.skip_btn)
        actions.addStretch(1)
        layout.addLayout(actions)

        buttons = QDialogButtonBox(self)
        self.apply_btn: QPushButton = buttons.addButton(
            "Apply selected", QDialogButtonBox.ButtonRole.AcceptRole
        )
        self.cancel_btn: QPushButton = buttons.addButton(
            "Cancel", QDialogButtonBox.ButtonRole.RejectRole
        )
        self.apply_btn.setObjectName("primary")
        self.apply_btn.setDefault(True)
        buttons.accepted.connect(self._on_apply_selected)
        buttons.rejected.connect(self._on_cancel)
        layout.addWidget(buttons)

        self.apply_all_btn.clicked.connect(self._on_apply_all)
        self.skip_btn.clicked.connect(self._on_cancel)

    # ── Result accessors ───────────────────────────────────────────────

    def selected_indices(self) -> list[int]:
        return list(self._selected_indices)

    # ── Slots ──────────────────────────────────────────────────────────

    def _on_apply_selected(self) -> None:
        self._selected_indices = [
            i for i in range(1, self._list.count() + 1)
            if self._list.item(i - 1).checkState() == Qt.CheckState.Checked
        ]
        self.accept()

    def _on_apply_all(self) -> None:
        self._selected_indices = list(range(1, self._list.count() + 1))
        self.accept()

    def _on_cancel(self) -> None:
        self._selected_indices = []
        self.reject()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)
