"""AdminNotifier — shows a one-shot non-modal warning when lil_bro is not elevated.

lil_bro needs Administrator rights to create a System Restore Point and apply system
fixes (registry, power plan, NVIDIA profile, etc.). The terminal entry point warns about
this via ``check_admin()`` (``src/bootstrapper.py``); the GUI surfaces the same warning
here, non-modally, so the user is informed without blocking startup.

Note: the LHM thermal sidecar fires its own UAC ``runas`` prompt at startup
(``src/collectors/sub/lhm_sidecar.py``), but that elevates ``lhm-server.exe`` only — the
lil_bro process itself stays unelevated, so the fix pipeline still needs this heads-up.

The dialog is built on the shared ``CardDialog`` template (object-name-driven QSS — see
``_qss_card_dialog`` in ``src/gui/theme/stylesheet_dialogs.py``), so it matches DESIGN.md
and the WASD "popout" convention: ``W`` / Enter trigger the default OK button, Esc
dismisses. It is shown non-modally (``.show()``, not ``.exec()``) so it never freezes
startup, with a once-guard so it appears at most once per session.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot

from src.gui.widgets.dialogs import CardDialog


class AdminWarningDialog(CardDialog):
    """Single-action warning that lil_bro is not running as Administrator.

    Thin specialization of the shared ``CardDialog`` template: a warning-tone card with
    a single "Got it" acknowledgement button (no secondary, so no WASD autoDefault case),
    shown non-modally so it never blocks startup. Styling lives in ``_qss_card_dialog``.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(
            "lil_bro isn't running as Administrator",
            "Creating a System Restore Point and applying system fixes will fail. "
            "For the full tune-up, close lil_bro and restart it as Administrator.",
            tone="warning",
            primary_label="Got it",
            modal=False,
            glow=True,
            parent=parent,
        )
        self.setWindowTitle("lil_bro — Administrator privileges")
        self.setAccessibleName("Administrator privileges warning")


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
