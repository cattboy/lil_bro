"""CapNotifier — shows a one-shot non-modal warning when the action log hits its cap.

The 100 MB cap on ``lil_bro_actions.log`` is enforced in
``ActionLogger._rotate_if_needed`` (``src/utils/action_logger.py``), which runs on the
pipeline **worker thread** while holding its lock. ``ActionLogger`` is deliberately
Qt-free, so it cannot show a dialog itself. Instead it calls an injected callback that
emits ``PipelineSignals.log_cap_reached``; that signal is connected to this slot with a
``QueuedConnection`` so the dialog is built and shown on the **main thread**.

This mirrors the ``StartupCompleter`` pattern in ``startup_coordinator.py``: PySide6
cannot reliably route a queued connection to a bare callable, so the slot lives on a
``QObject`` anchored to the main window's thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Slot
from PySide6.QtWidgets import QMessageBox


class CapNotifier(QObject):
    """Shows a one-shot NON-MODAL critical popup when the action log hits its cap.

    Lives on the main thread (parented to the main window); driven by a queued signal so
    the worker thread that detects the cap never touches a widget. The dialog is shown
    non-modally (``.show()``, not ``.exec()``) so a cap event during a running pipeline
    does not freeze the UI.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._box: QMessageBox | None = None  # kept alive while shown; also the once-guard

    @Slot()
    def show_cap_reached(self) -> None:
        if self._box is not None:
            return  # already shown this session
        box = QMessageBox(self.parent())
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle("lil_bro — action log full")
        box.setText(
            "lil_bro_actions.log has exceeded the 100 MB cap and logging has stopped.\n\n"
            "Please remove the file and restart lil_bro."
        )
        box.setWindowModality(Qt.WindowModality.NonModal)
        self._box = box  # hold a reference so it isn't garbage-collected on return
        box.show()  # non-blocking; does not freeze the pipeline
