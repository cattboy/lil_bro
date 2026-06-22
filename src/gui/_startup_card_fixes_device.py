"""Monitor + NVIDIA dashboard card fixes, extracted from StartupCoordinator.

A mixin folded into ``StartupCoordinator`` (a ``QObject``) so the card-fix
worker QThreads' cross-thread ``finished`` / ``result`` slots anchor to the GUI
thread. Each request handler gathers approval on the GUI thread, then spawns a
worker on its own ``QThread``; the cleanup slots clear the in-progress guards.
Shared helpers ``_ensure_restore_point_choice`` and ``_on_card_fix_result`` stay
on the core coordinator and resolve via the composed MRO. No ``__init__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Slot


class DeviceFixMixin:
    """Monitor refresh-rate + NVIDIA profile/DLSS card-fix handlers."""

    if TYPE_CHECKING:
        # Provided by StartupCoordinator.__init__ (mixin; type-checker only).
        _main: Any
        _runtime: dict
        _log: Any
        _monitor_fix_device: Any
        _nvidia_fix_check_name: Any

        # Shared helpers on the core coordinator + a sibling-mixin slot, resolved
        # via the composed coordinator's MRO.
        def _ensure_restore_point_choice(self, parent) -> bool: ...
        def _on_card_fix_result(self, check_name: str, ok: bool) -> None: ...
        def refresh_monitor_card(self) -> None: ...

    def on_monitor_fix_requested(self, device: str) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
        # Guard: dashboard fix during a pipeline run races ApplyPhase's
        # _fix_display -- concurrent ChangeDisplaySettingsExW + concurrent
        # manifest appends would record the wrong "before" state and break revert.
        if runtime.get("pipeline_thread") is not None:
            log.warning("Monitor fix suppressed: pipeline is running")
            return
        # Guard: only one card fix at a time. Prevents concurrent NPI imports,
        # double restore-point creation, and manifest-write races.
        if runtime.get("card_fix_in_progress"):
            log.warning("Monitor fix suppressed: a card fix is already in progress")
            return
        specs = runtime.get("preloaded_specs", {}) or {}
        displays = specs.get("DisplayCapabilities", []) or []
        target = next((d for d in displays if d.get("device") == device), None)
        if target is None:
            log.warning("Monitor fix requested for unknown device: %s", device)
            return
        desc = (
            f"{device}: Current {target.get('current_refresh_hz', '?')}Hz  →  "
            f"Max {target.get('max_refresh_hz', '?')}Hz at {target.get('at_resolution', '')}"
        )
        proposal = {
            "finding": "display",
            "title": "Set Monitor to Maximum Refresh Rate",
            "sev": "medium",
            "desc": desc,
            "can_auto_fix": True,
            "mode": "AUTO",
            "tag": "DISPLAY",
        }
        from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
        dialog = BatchSelectionDialog([proposal], parent=main)
        if not dialog.exec() or not dialog.selected_indices():
            return
        # Restore-point gate (shared across all dashboard card fixes). Approval
        # collected here on the GUI thread; the worker creates it non-interactively.
        create_rp = self._ensure_restore_point_choice(main)
        # Filter so _fix_display targets ONLY this device
        filtered_specs = {**specs, "DisplayCapabilities": [target]}
        from src.gui.worker import _MonitorFixWorker
        fix_thread = QThread()
        fix_worker = _MonitorFixWorker(filtered_specs, create_rp)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(self.refresh_monitor_card)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        fix_worker.result.connect(self._on_monitor_fix_result)
        runtime["monitor_fix_thread"] = fix_thread
        runtime["monitor_fix_worker"] = fix_worker
        runtime["card_fix_in_progress"] = True
        if create_rp:
            runtime["restore_point_in_progress"] = True
        fix_thread.finished.connect(self._on_monitor_fix_thread_finished)
        # In-flight feedback: lock this monitor's Fix button + light the status
        # bar. Store the device so the finished slot can route the reset back to
        # the same card (multi-monitor).
        self._monitor_fix_device = device
        main._dashboard.set_fix_card_applying("display", True, device)
        main.status_bar_widget.set_state("run", "Applying display fix…")
        fix_thread.start()

    def on_nvidia_fix_requested(self, check_name: str) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
        # Guard: a dashboard NVIDIA fix during a pipeline run races ApplyPhase's
        # nvidia_profile fix -- concurrent NPI imports + manifest appends.
        if runtime.get("pipeline_thread") is not None:
            log.warning("NVIDIA fix suppressed: pipeline is running")
            return
        # Guard: only one card fix at a time. Prevents concurrent NPI imports,
        # double restore-point creation, and manifest-write races.
        if runtime.get("card_fix_in_progress"):
            log.warning("NVIDIA fix suppressed: a card fix is already in progress")
            return
        specs = runtime.get("preloaded_specs", {}) or {}
        nvidia = specs.get("NVIDIA", [])
        if not isinstance(nvidia, list) or not nvidia:
            log.warning("NVIDIA fix requested but no NVIDIA GPU in specs")
            return

        gpu_name = str(nvidia[0].get("GPU") or "your NVIDIA GPU")
        if check_name == "nvidia_dlss_preset":
            from src.utils.dlss_presets import get_preset
            preset = get_preset(gpu_name)
            letter = preset.letter if preset is not None else "?"
            title = f"Set DLSS Preset {letter}"
            desc = (
                f"{gpu_name}: force DLSS Preset {letter} (the recommended AI upscaling "
                f"model for your GPU). Changes ONLY the DLSS preset — "
                f"All changes revertable and backed up, lil_bro has your back"
            )
            tag = "NVIDIA DLSS"
        else:  # nvidia_profile (full)
            title = "Optimize NVIDIA Driver Profile"
            desc = (
                f"{gpu_name}: apply the Nvidia Profile Inspector gaming profile (MORE FPS) — "
                f"enables G-Sync, VSync, FPS cap, ReBar, "
                f"and Maximum Performance power mode. All changes revertable and backed up "
                f"with lil_bro looking out"
            )
            tag = "NVIDIA"

        proposal = {
            "finding": check_name,
            "title": title,
            "sev": "medium",
            "desc": desc,
            "can_auto_fix": True,
            "mode": "AUTO",
            "tag": tag,
        }
        from src.gui.widgets.batch_selection_dialog import BatchSelectionDialog
        dialog = BatchSelectionDialog([proposal], parent=main)
        if not dialog.exec() or not dialog.selected_indices():
            return

        # Restore-point gate (shared with the monitor fix). Approval collected
        # here on the GUI thread; the worker creates it non-interactively.
        create_rp = self._ensure_restore_point_choice(main)

        # Filter so the handler only sees the NVIDIA payload.
        filtered_specs = {**specs, "NVIDIA": nvidia}
        self._nvidia_fix_check_name = check_name
        from src.gui.worker import _CardFixWorker
        fix_thread = QThread()
        fix_worker = _CardFixWorker(check_name, filtered_specs, create_rp)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        fix_worker.result.connect(self._on_nvidia_fix_result)
        runtime["nvidia_fix_thread"] = fix_thread
        runtime["nvidia_fix_worker"] = fix_worker
        runtime["card_fix_in_progress"] = True
        if create_rp:
            runtime["restore_point_in_progress"] = True
        fix_thread.finished.connect(self._on_nvidia_fix_thread_finished)
        # In-flight feedback: lock the card's button + light the status bar
        # before the worker blocks on the NPI export/import (3-10s).
        main._dashboard.set_fix_card_applying(check_name, True)
        main.status_bar_widget.set_state("run", f"Applying {tag} fix…")
        fix_thread.start()

    @Slot(bool)
    def _on_monitor_fix_result(self, ok: bool) -> None:
        """Queued (main-thread) wrapper for the monitor card-fix result."""
        self._on_card_fix_result("display", ok)

    @Slot(bool)
    def _on_nvidia_fix_result(self, ok: bool) -> None:
        """Queued (main-thread) wrapper for the NVIDIA card-fix result.

        Reads the check_name captured in on_nvidia_fix_requested rather than
        self.sender() -- the latter is unreliable for queued connections and
        risks dereferencing a deleteLater-d worker.
        """
        check_name = self._nvidia_fix_check_name or "nvidia_profile"
        self._on_card_fix_result(check_name, ok)
        if ok and check_name == "nvidia_profile":
            self._main._dashboard.set_nvidia_profile_findings({"status": "OK"})

    @Slot()
    def _on_monitor_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("monitor_fix_thread", None)
        runtime.pop("monitor_fix_worker", None)
        # Reset the busy cue on the monitor card that was fixed (routed by the
        # device stored at request time) + the status bar. refresh_monitor_card
        # (connected earlier on thread.finished) has already re-evaluated the
        # button's visibility; re-enabling a hidden button is harmless.
        try:
            self._main._dashboard.set_fix_card_applying(
                "display", False, self._monitor_fix_device
            )
            self._main.status_bar_widget.set_state("ok", "Idle")
        except Exception:
            pass

    @Slot()
    def _on_nvidia_fix_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("card_fix_in_progress", None)
        runtime.pop("restore_point_in_progress", None)
        runtime.pop("nvidia_fix_thread", None)
        runtime.pop("nvidia_fix_worker", None)
        # Reset the busy cue (button + status bar) for BOTH success and failure
        # -- thread.finished fires either way. Route via the stored check_name
        # (sender() is unreliable for queued connections). Best-effort so a UI
        # reset failure can't strand the guard pops above.
        try:
            self._main._dashboard.set_fix_card_applying(
                self._nvidia_fix_check_name or "nvidia_profile", False
            )
            self._main.status_bar_widget.set_state("ok", "Idle")
        except Exception:
            pass
