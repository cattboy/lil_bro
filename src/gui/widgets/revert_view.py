"""Revert page — displays applied fixes and lets the user trigger a revert.

The RevertView is a dedicated page (QStackedWidget index 2) that shows:
  - A description header explaining the revert flow
  - LastRunCard: read-only list of fixes applied this session
  - A prominent "Revert Changes" action button

Navigation: the sidebar "↩ Revert Changes" button navigates to this page.
Clicking the in-page revert button emits ``revert_requested`` — wired in
``app.py`` to ``PipelineController.start_revert()``.

The ``LastRunCard`` slot is pre-allocated here (not created on-demand) for the
same reason as the monitor slots in ``dashboard.py``: dynamic widget creation
during ``splash.exec()``'s nested event loop fails to parent correctly in the
bundled PyInstaller exe.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.gui.widgets.last_run_card import LastRunCard
from src.utils.debug_logger import get_debug_logger


class RevertView(QWidget):
    """Dedicated revert page: shows applied fixes and a revert action button."""

    revert_requested = Signal()
    system_restore_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAccessibleName("Revert view")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 20)
        outer.setSpacing(12)

        # ── Header card ──────────────────────────────────────────────────
        header_frame = QFrame()
        header_frame.setObjectName("chartWrap")
        hdr_v = QVBoxLayout(header_frame)
        hdr_v.setContentsMargins(20, 16, 20, 16)
        hdr_v.setSpacing(6)

        hdr_inner = QFrame()
        hdr_inner.setObjectName("chartHeader")
        hdr_row = QHBoxLayout(hdr_inner)
        hdr_row.setContentsMargins(0, 0, 0, 0)

        title_lbl = QLabel("REVERT CHANGES")
        title_lbl.setObjectName("chartTitle")
        hdr_row.addWidget(title_lbl)
        hdr_row.addStretch()

        hdr_v.addWidget(hdr_inner)

        desc_lbl = QLabel(
            "Review the fixes applied this session. "
            "Click Revert Changes to restore your original settings."
        )
        desc_lbl.setObjectName("pollStatus")
        desc_lbl.setWordWrap(True)
        hdr_v.addWidget(desc_lbl)

        outer.addWidget(header_frame)

        # ── Applied Fixes card (PRE-ALLOCATED) ───────────────────────────
        # Pre-allocated in __init__ for the same reason as the monitor slots
        # in dashboard.py: dynamic creation during splash.exec() fails to
        # parent correctly in the bundled exe. Hidden until set_last_run()
        # finds a session manifest with fixes to display.
        self._last_run_card = LastRunCard(parent=self)
        self._last_run_card.hide()
        outer.addWidget(self._last_run_card)

        # ── No-fixes placeholder ─────────────────────────────────────────
        self._no_fixes_lbl = QLabel("No applied fixes found for this session.")
        self._no_fixes_lbl.setObjectName("pollStatus")
        self._no_fixes_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self._no_fixes_lbl)

        # ── Revert action button ─────────────────────────────────────────
        btn_wrap = QFrame()
        btn_wrap.setObjectName("chartWrap")
        btn_v = QVBoxLayout(btn_wrap)
        btn_v.setContentsMargins(20, 16, 20, 16)

        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._revert_btn = QPushButton("↩  Revert All Changes (R)")
        self._revert_btn.setObjectName("revertActionBtn")
        self._revert_btn.setProperty("navRole", "nav")
        self._revert_btn.setProperty("navState", "warning")
        self._revert_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._revert_btn.setMinimumHeight(40)
        self._revert_btn.setMinimumWidth(200)
        self._revert_btn.clicked.connect(self.revert_requested)
        btn_row.addWidget(self._revert_btn)

        btn_v.addLayout(btn_row)
        outer.addWidget(btn_wrap)

        # ── System Restore card (the big undo) ────────────────────────────
        # Always visible: System Restore is a general Windows feature, not tied
        # to whether lil_bro made a restore point this session. The button only
        # emits system_restore_requested; the confirm dialog + rstrui.exe launch
        # live in PipelineController.open_system_restore (wired in app.py).
        restore_wrap = QFrame()
        restore_wrap.setObjectName("chartWrap")
        restore_v = QVBoxLayout(restore_wrap)
        restore_v.setContentsMargins(20, 16, 20, 16)
        restore_v.setSpacing(6)

        restore_hdr = QLabel("SYSTEM RESTORE — THE BIG UNDO")
        restore_hdr.setObjectName("pollLabel")
        restore_v.addWidget(restore_hdr)

        restore_desc = QLabel(
            "If reverting the fixes above isn't enough, Windows System Restore "
            "rolls your entire PC back to the snapshot lil_bro saved before "
            "tuning. This undoes everything since that point — not just lil_bro's "
            "changes — and requires a restart. Click the button, pick the point "
            "named \"lil_bro Pre-Tuning <date>\", and follow Windows' prompts."
        )
        restore_desc.setObjectName("pollStatus")
        restore_desc.setWordWrap(True)
        restore_v.addWidget(restore_desc)

        restore_row = QHBoxLayout()
        restore_row.addStretch()

        self._restore_btn = QPushButton("↻  Open System Restore")
        self._restore_btn.setObjectName("openRestoreBtn")
        self._restore_btn.setProperty("navRole", "nav")
        self._restore_btn.setProperty("navState", "warning")
        self._restore_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._restore_btn.setMinimumHeight(40)
        self._restore_btn.setMinimumWidth(200)
        self._restore_btn.clicked.connect(self.system_restore_requested)
        restore_row.addWidget(self._restore_btn)

        restore_v.addLayout(restore_row)
        outer.addWidget(restore_wrap)

        outer.addStretch(1)

        self._log = get_debug_logger()

    # ── Public API ──────────────────────────────────────────────────────

    def set_last_run(self, manifest: object) -> None:
        """Feed the session manifest into the Applied Fixes card.

        Shows the card when the manifest has applied fixes to display, hides
        it otherwise. Toggles the no-fixes placeholder accordingly. Runs on
        the GUI thread, so direct mutation is safe.
        """
        visible = self._last_run_card.set_manifest(manifest)
        self._last_run_card.setVisible(visible)
        self._no_fixes_lbl.setVisible(not visible)
        self._log.debug("RevertView.set_last_run: card visible=%s", visible)

    def set_revert_enabled(self, enabled: bool) -> None:
        """Enable or disable the in-page revert action button."""
        self._revert_btn.setEnabled(enabled)
