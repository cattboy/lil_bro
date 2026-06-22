"""Startup orchestration coordinator for the GUI.

Extracted from ``app.run()``'s closure: owns the StartupOrchestrator
step / lhm-ready / finished handlers and the monitor-refresh-card
handlers. ``app.run()`` constructs one instance and routes the
orchestrator + dashboard signals to its methods.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Slot

# Re-exported so existing imports (tests + pipeline_controller) keep resolving
# against this module after the map moved to a leaf module.
from src.gui._startup_sections import (  # noqa: F401
    _FIX_TO_SECTIONS,
    _sections_for_fixes,
)
from src.gui._startup_manifest_watcher import ManifestWatcherMixin
from src.gui._startup_wiring import StartupWiringMixin
from src.gui._startup_dashboard_refresh import DashboardRefreshMixin
from src.gui._startup_card_fixes_device import DeviceFixMixin
from src.gui._startup_card_fixes_setting import SettingThermalFixMixin


class StartupCompleter(QObject):
    """Hosts an orchestrator slot on the main thread.

    PySide6 cannot reliably route a QueuedConnection to a bare callable -- the
    queued event needs a QObject receiver to anchor it to a thread's event
    loop. Wrapping the slot in a QObject parented to ``main`` guarantees
    main-thread delivery.
    """

    def __init__(self, on_done, parent=None) -> None:
        super().__init__(parent)
        self._on_done = on_done

    @Slot(object)
    def on_finished(self, startup_lhm) -> None:
        self._on_done(startup_lhm)


class StartupCoordinator(
    SettingThermalFixMixin,
    DeviceFixMixin,
    DashboardRefreshMixin,
    StartupWiringMixin,
    ManifestWatcherMixin,
    QObject,
):
    """Owns the StartupOrchestrator + monitor-refresh-card signal handlers.

    Constructed once by ``app.run()``; the shared ``runtime`` dict is stored
    by reference. ``pipeline`` is the PipelineController -- ``on_finished``
    re-enables the flow controls through it once startup completes.
    """

    def __init__(self, main, runtime: dict, log, orchestrator, pipeline, parent=None) -> None:
        # QObject base anchors this coordinator's slots to the thread it is built
        # on (the main/GUI thread). Without it, the card-fix worker QThreads'
        # cross-thread signals (fix_thread.finished, worker.result) fall back to
        # DirectConnection and run on the dying worker thread -- stranding the
        # card_fix_in_progress cleanup (dashboard locks) and mutating widgets
        # off-thread (parent=None). See StartupCompleter for the same rationale.
        super().__init__(parent)
        self._main = main
        self._runtime = runtime
        self._log = log
        self._orchestrator = orchestrator
        self._pipeline = pipeline
        # NVIDIA card-fix check_name, captured at request time so the queued
        # result slot reads it without a fragile self.sender() lookup on a
        # possibly-deleted worker.
        self._nvidia_fix_check_name: str | None = None
        # Power Plan / Game Mode card-fix check_name -- same capture-at-request
        # rationale as _nvidia_fix_check_name.
        self._setting_fix_check_name: str | None = None
        # Monitor card-fix device, captured at request time (same rationale as above).
        self._monitor_fix_device: str | None = None
        # Applied Fixes card (T-016): a QFileSystemWatcher refreshes it live; a
        # single-shot QTimer debounces the double directoryChanged per write.
        self._last_run_watcher = None
        self._last_run_debounce = None
        self._last_manifest_sig = None
        self._init_last_run_watcher()

    def _ensure_restore_point_choice(self, parent) -> bool:
        """GUI-thread gate: decide whether the worker should create a restore point.

        Returns True only when no restore point exists yet this session (per the
        session manifest) AND the user accepts the prompt. The actual creation
        runs non-interactively in the fix worker via
        ``create_restore_point(assume_approved=True)`` -- collecting approval
        here (not in the worker) avoids the ``prompt_approval`` deadlock in the
        event-loop-less worker thread. The pipeline's BootstrapPhase consults the
        same manifest flag, so a card-created restore point isn't asked for twice.
        """
        from src.utils.revert import load_manifest
        manifest = load_manifest()
        if manifest is not None and manifest.get("restore_point_created"):
            return False  # already created this session; pipeline + cards reuse it
        from src.gui.widgets.confirm_dialog import ConfirmDialog
        dlg = ConfirmDialog(
            "Create a System Restore Point?",
            "Recommended before changing system settings — it lets you roll back if "
            "anything goes wrong. Created once per session (this may take a minute).",
            parent=parent,
            yes_label="Create Restore Point",
            no_label="Skip",
        )
        return bool(dlg.exec())

    def _on_card_fix_result(self, check_name: str, ok: bool) -> None:
        """Show an error dialog if a dashboard card fix failed."""
        if not ok:
            from src.gui.widgets.dialogs import CardDialog
            CardDialog(
                "Fix failed",
                f"The {check_name} fix did not complete. Check the debug log for details.",
                tone="error",
                parent=self._main,
            ).exec()
