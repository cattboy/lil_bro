"""Multi-select dialog mirroring CLI ``run_approval_flow`` batch input.

CLI parses ``"1 3"`` / ``"all"`` / ``"skip"``. The GUI replaces that
single-line prompt with a checkable list + three actions:

- Apply selected → return the list of selected 1-based indices
- Apply all → return ``[1..n]``
- Skip / Esc → return ``[]``

Each row is numbered (1-based) to mirror the CLI list; pressing the matching
digit key (1-9) toggles that fix's selection.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.theme import repolish

class _FixItem(QFrame):
    """One clickable fix row: checkbox, sev badge, title/desc, AUTO/MANUAL tag."""

    toggled = Signal()

    def __init__(self, idx: int, proposal: dict, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("fixItem")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        sev = (proposal.get("sev") or proposal.get("severity") or "low").lower()
        tag = (proposal.get("tag") or proposal.get("category") or "").upper()
        title = proposal.get("title") or proposal.get("finding") or f"Proposal {idx + 1}"
        desc = proposal.get("desc") or proposal.get("description") or proposal.get("explanation") or ""
        mode = "AUTO" if proposal.get("can_auto_fix", True) else "MANUAL"
        mode = proposal.get("mode", mode)

        self._selected = True
        self.setProperty("selected", "true")

        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(10)

        # 1-based option number, mirroring the CLI's numbered batch list
        # ("1 3"). Pressing the matching digit toggles this row -- see
        # BatchSelectionDialog.keyPressEvent.
        self._num_lbl = QLabel(str(idx + 1))
        self._num_lbl.setObjectName("fixNum")
        self._num_lbl.setFixedSize(22, 22)
        self._num_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._num_lbl, alignment=Qt.AlignmentFlag.AlignTop)

        self._check_lbl = QLabel("✓")
        self._check_lbl.setObjectName("checkBox")
        self._check_lbl.setProperty("checked", "true")
        self._check_lbl.setFixedSize(22, 22)
        self._check_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self._check_lbl, alignment=Qt.AlignmentFlag.AlignTop)

        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        sev_text = f"{sev.upper()}" + (f"  ·  {tag}" if tag else "")
        sev_lbl = QLabel(sev_text)
        sev_lbl.setObjectName("fixSev")
        sev_lbl.setProperty("sev", sev)
        info_col.addWidget(sev_lbl)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("fixTitle")
        title_lbl.setWordWrap(True)
        info_col.addWidget(title_lbl)

        if desc:
            desc_lbl = QLabel(desc)
            desc_lbl.setObjectName("fixDesc")
            desc_lbl.setWordWrap(True)
            info_col.addWidget(desc_lbl)

        row.addLayout(info_col, stretch=1)

        mode_lbl = QLabel(mode)
        mode_lbl.setObjectName("modeBadge")
        mode_lbl.setProperty("mode", mode)
        row.addWidget(mode_lbl, alignment=Qt.AlignmentFlag.AlignTop)

    @property
    def is_selected(self) -> bool:
        return self._selected

    def toggle(self) -> None:
        """Flip selection state and refresh the row's QSS + checkbox glyph."""
        self._selected = not self._selected
        self.setProperty("selected", "true" if self._selected else "false")
        self._check_lbl.setText("✓" if self._selected else "")
        self._check_lbl.setProperty("checked", "true" if self._selected else "false")
        repolish(self._check_lbl)
        repolish(self)
        self.toggled.emit()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.toggle()
        super().mousePressEvent(event)


class BatchSelectionDialog(QDialog):
    """V2 fix-list approval dialog with severity badges and AUTO/MANUAL tags."""

    def __init__(self, proposals: list[dict], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply These Fixes?")
        self.setObjectName("batchDialog")
        self.setModal(True)
        # Two columns when there is more than one fix: halves the card stack's
        # height so the footer (Apply/Skip) stays on screen for long lists. A
        # lone fix keeps the narrower single-column width.
        self.setFixedWidth(820 if len(proposals) > 1 else 540)
        self.setAccessibleName("Batch selection dialog")

        self._proposals = proposals
        self._selected: list[bool] = [True] * len(proposals)
        self._selected_indices: list[int] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setObjectName("dlgHead")
        hdr_row = QHBoxLayout(hdr)
        hdr_row.setContentsMargins(20, 16, 16, 16)

        title_lbl = QLabel("Apply These Fixes?")
        title_lbl.setObjectName("dlgTitle")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("secondary")
        close_btn.setFixedSize(28, 28)
        close_btn.setAutoDefault(False)
        close_btn.clicked.connect(self.reject)
        hdr_row.addWidget(close_btn)

        layout.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────
        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(20, 8, 20, 8)
        body_layout.setSpacing(8)

        count = len(proposals)
        subtitle = QLabel(f"lil_bro identified {count} improvement{'s' if count != 1 else ''}. "
                          f"Click a row or press its number (1-9) to toggle:")
        subtitle.setObjectName("dlgSubtitle")
        subtitle.setWordWrap(True)
        body_layout.addWidget(subtitle)

        # Fix cards in a grid, filled left-to-right then top-to-bottom. Two
        # columns once there is more than one fix; a single fix stays in one
        # column so it isn't stranded beside an empty cell.
        cols = 2 if count > 1 else 1
        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self._fix_items: list[_FixItem] = []
        for i, proposal in enumerate(proposals):
            item = _FixItem(i, proposal, self)
            item.toggled.connect(lambda idx=i: self._on_item_toggled(idx))
            self._fix_items.append(item)
            grid.addWidget(item, i // cols, i % cols)

        for c in range(cols):
            grid.setColumnStretch(c, 1)

        body_layout.addLayout(grid)

        layout.addWidget(body)

        # ── Footer ────────────────────────────────────────────────────
        foot = QFrame()
        foot.setObjectName("dlgFoot")
        foot_row = QHBoxLayout(foot)
        foot_row.setContentsMargins(20, 12, 20, 16)
        foot_row.setSpacing(8)
        foot_row.addStretch()

        self._skip_btn = QPushButton("Skip All (S)")
        self._skip_btn.setObjectName("secondary")
        self._skip_btn.setAutoDefault(False)
        self._skip_btn.clicked.connect(self.reject)

        self._apply_btn = QPushButton(f"Apply {count} Selected (W)")
        self._apply_btn.setObjectName("primary")
        self._apply_btn.setDefault(True)
        self._apply_btn.clicked.connect(self.accept)

        foot_row.addWidget(self._skip_btn)
        foot_row.addWidget(self._apply_btn)

        layout.addWidget(foot)

    # ── State sync ─────────────────────────────────────────────────────

    def _on_item_toggled(self, idx: int) -> None:
        self._selected[idx] = self._fix_items[idx].is_selected
        count = sum(self._selected)
        self._apply_btn.setText(f"Apply {count} Selected (W)")
        self._apply_btn.setEnabled(count > 0)

    # ── Result accessors ───────────────────────────────────────────────

    def selected_indices(self) -> list[int]:
        return list(self._selected_indices)

    # ── Accept / reject / key handling ─────────────────────────────────

    def accept(self) -> None:
        self._selected_indices = [i + 1 for i, sel in enumerate(self._selected) if sel]
        super().accept()

    def reject(self) -> None:
        self._selected_indices = []
        super().reject()

    def keyPressEvent(self, event):  # noqa: N802
        key = event.key()
        if key in (Qt.Key.Key_Escape, Qt.Key.Key_S):
            self.reject()
            return
        if key == Qt.Key.Key_W:
            self.accept()
            return
        # Number keys 1-9 toggle the matching fix, mirroring the CLI's "1 3"
        # batch input. Lists longer than 9 fall through past the 9th row --
        # those rows stay toggleable by mouse.
        if Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            idx = key - Qt.Key.Key_1
            if idx < len(self._fix_items):
                self._fix_items[idx].toggle()
                return
        super().keyPressEvent(event)
