"""AdminNotifier — shows a one-shot non-modal warning when lil_bro is not elevated.

lil_bro needs Administrator rights to create a System Restore Point and apply system
fixes (registry, power plan, NVIDIA profile, etc.). The terminal entry point warns about
this via ``check_admin()`` (``src/bootstrapper.py``); the GUI surfaces the same warning
here, non-modally, so the user is informed without blocking startup.

Note: the LHM thermal sidecar fires its own UAC ``runas`` prompt at startup
(``src/collectors/sub/lhm_sidecar.py``), but that elevates ``lhm-server.exe`` only — the
lil_bro process itself stays unelevated, so the fix pipeline still needs this heads-up.

The dialog is a styled custom ``QDialog`` (object-name-driven QSS — see ``_qss_admin_dialog``
in ``src/gui/theme/stylesheet_dialogs.py``) following the project's dialog template
(``ConfirmDialog`` / ``MouseReadyDialog``), so it matches DESIGN.md and the WASD "popout"
convention: ``W`` / Enter trigger the default OK button, Esc dismisses. It is shown
non-modally (``.show()``, not ``.exec()``) so it never freezes startup, with a once-guard so
it appears at most once per session.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class AdminWarningDialog(QDialog):
    """Single-action warning that lil_bro is not running as Administrator.

    Mirrors the ``ConfirmDialog`` template (icon + title + description header, accent-glow
    primary button) but with a single OK button -- it is an acknowledgement, not a choice,
    so there is no secondary button (and thus no WASD autoDefault-theft case to guard).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        # objectName drives the elevated "card" styling (surface bg + border + 12px
        # radius) -- see _qss_admin_dialog in stylesheet_dialogs.py.
        self.setObjectName("adminDialog")
        self.setWindowTitle("lil_bro — Administrator privileges")
        self.setModal(False)  # non-modal: never blocks startup or the pipeline
        self.setFixedWidth(420)
        self.setAccessibleName("Administrator privileges warning")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        # ── Icon + text row ──────────────────────────────────────────
        body_row = QHBoxLayout()
        body_row.setSpacing(14)
        body_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        icon = QLabel("⚠")
        icon.setObjectName("adminIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        body_row.addWidget(icon, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        title_lbl = QLabel("lil_bro isn't running as Administrator")
        title_lbl.setObjectName("adminTitle")
        title_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)

        desc_lbl = QLabel(
            "Creating a System Restore Point and applying system fixes will fail. "
            "For the full tune-up, close lil_bro and restart it as Administrator."
        )
        desc_lbl.setObjectName("adminDesc")
        desc_lbl.setWordWrap(True)
        text_col.addWidget(desc_lbl)

        body_row.addLayout(text_col)
        layout.addLayout(body_row)

        # ── Button ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        ok_btn = QPushButton("Got it (W)")
        ok_btn.setObjectName("primary")
        ok_btn.setDefault(True)  # W / Enter trigger it via the WASD popout filter
        ok_btn.clicked.connect(self.accept)
        # Accent glow makes the primary button the focal point, per DESIGN.md
        # ("primary accent elements get a soft glow"); QSS can't do box-shadow, so we
        # use a drop-shadow effect with the accent colour (matches ConfirmDialog).
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(24)
        glow.setColor(QColor(0, 229, 204, 150))  # accent #00E5CC, soft alpha
        glow.setOffset(0, 0)
        ok_btn.setGraphicsEffect(glow)

        btn_row.addWidget(ok_btn)
        layout.addLayout(btn_row)

    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)


class AdminNotifier(QObject):
    """Shows a one-shot NON-MODAL warning when lil_bro is not running as Administrator."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dialog: AdminWarningDialog | None = None  # kept alive while shown; also the once-guard

    @Slot()
    def show_warning(self) -> None:
        if self._dialog is not None:
            return  # already shown this session
        dialog = AdminWarningDialog(self.parent())
        self._dialog = dialog  # hold a reference so it isn't garbage-collected on return
        dialog.show()  # non-blocking; does not freeze startup or the pipeline
