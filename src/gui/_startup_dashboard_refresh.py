"""Dashboard fix-card live re-collect, extracted from StartupCoordinator.

A mixin folded into ``StartupCoordinator`` (a ``QObject``) so its worker-thread
result slots anchor to the GUI thread. Owns the monitor card re-probe and the
generalized fix-card rescan -- the shared post-apply path used by both the
optimization pipeline and a revert. No ``__init__``; all state is set by
``StartupCoordinator.__init__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QThread, Slot


class DashboardRefreshMixin:
    """Monitor card + fix-card live re-collect handlers."""

    if TYPE_CHECKING:
        # Provided by StartupCoordinator.__init__ (mixin; type-checker only).
        _main: Any
        _runtime: dict
        _log: Any

    @Slot()
    def refresh_fix_cards_after_revert(self) -> None:
        """Re-scan the Dashboard fix cards after a revert.

        A revert restores the pre-apply settings, but the cards may be showing
        the optimistic "applied" state (card fixes) or the post-run state (the
        cached ``preloaded_specs`` is refreshed after a pipeline run). Delegates
        to the shared live re-collect so the cards reflect the real, just-reverted
        system state -- the same path used after the optimization pipeline, so the
        two surfaces never diverge.

        ``start_revert`` captured the reverted fixes' sections in
        ``_revert_refresh_scope`` before the manifest was deleted, so only those
        cards are re-collected; falls back to a full refresh when unset.

        Wired to RevertWorker.revert_finished from PipelineController.start_revert.
        This coordinator is a QObject on the GUI thread, so the cross-thread
        signal delivers here as a QueuedConnection -- safe to spawn the worker.
        """
        scope = self._runtime.pop("_revert_refresh_scope", None)
        self.refresh_dashboard_fix_cards(scope)

    def refresh_monitor_card(self) -> None:
        """Re-probe monitor capabilities on a worker thread.

        get_monitor_refresh_capabilities() runs EnumDisplayDevicesW + an
        optional WMI fallback, blocking for 200-800 ms. Doing that on the
        GUI thread janks the dashboard when the user clicks Refresh or
        when this fires off fix_thread.finished after a monitor fix.
        Result is applied to the UI from _on_refresh_result on the main
        thread.
        """
        runtime = self._runtime
        # Guard: refresh during a pipeline run could mutate
        # runtime["preloaded_specs"]["DisplayCapabilities"] while
        # PipelineWorker is still iterating ctx.specs (which aliases the
        # same dict in the snapshot-fallback path from phase_scan). Same
        # shape of bug as CR-1 for on_monitor_fix_requested.
        if runtime.get("pipeline_thread") is not None:
            self._log.warning("Monitor refresh suppressed: pipeline is running")
            return
        if runtime.get("monitor_refresh_thread") is not None:
            return  # already in-flight; the existing worker will deliver the result
        from src.gui.worker import _MonitorRefreshWorker
        refresh_thread = QThread()
        refresh_worker = _MonitorRefreshWorker()
        refresh_worker.moveToThread(refresh_thread)
        refresh_thread.started.connect(refresh_worker.run)
        refresh_worker.finished.connect(self._on_refresh_result)
        refresh_worker.failed.connect(self._on_refresh_failed)
        refresh_worker.finished.connect(refresh_thread.quit)
        refresh_worker.failed.connect(refresh_thread.quit)
        refresh_thread.finished.connect(refresh_worker.deleteLater)
        refresh_thread.finished.connect(refresh_thread.deleteLater)
        refresh_thread.finished.connect(self._on_refresh_thread_finished)
        runtime["monitor_refresh_thread"] = refresh_thread
        runtime["monitor_refresh_worker"] = refresh_worker
        refresh_thread.start()


    def refresh_dashboard_fix_cards(self, scope: set[str] | None = None) -> None:
        """Re-collect the fix-relevant spec sections on a worker thread and
        repopulate the affected Dashboard fix cards.

        Generalizes the monitor card's post-fix live re-probe
        (``refresh_monitor_card``) to all fix cards. The cards are built once at
        startup from the cached ``preloaded_specs`` snapshot; after the pipeline
        (or a revert) mutates the system that snapshot is stale and the cards
        keep showing old data / offering already-applied fixes.

        ``scope`` is the set of spec-section keys to re-collect (derived from the
        session's applied fixes via ``_sections_for_fixes``):
          * ``None``      -> re-collect every fix section (full refresh / fallback).
          * a non-empty set -> re-collect only those sections (and repaint only
            their cards) -- e.g. skip the slow NVIDIA export when no NVIDIA fix ran.
          * an empty set  -> nothing changed this session; do nothing.

        Re-collection runs through the same ``collect_fix_sections`` collectors and
        the same analyzers the startup wiring uses -- one source of truth shared by
        the Dashboard and the optimization flow.
        """
        runtime = self._runtime
        if scope is not None and not scope:
            self._log.info("Dashboard rescan skipped: no fix sections changed this session")
            return
        # Revert and pipeline are mutually exclusive; this fires from
        # pipeline-finished (after the thread is cleared) and revert-finished.
        if runtime.get("pipeline_thread") is not None:
            self._log.warning("Dashboard rescan suppressed: pipeline is running")
            return
        if runtime.get("dashboard_rescan_thread") is not None:
            return  # already in-flight; the existing worker will deliver the result
        from src.gui.worker import _DashboardRescanWorker
        rescan_thread = QThread()
        rescan_worker = _DashboardRescanWorker(sections=scope)
        rescan_worker.moveToThread(rescan_thread)
        rescan_thread.started.connect(rescan_worker.run)
        rescan_worker.finished.connect(self._on_dashboard_rescan_result)
        rescan_worker.failed.connect(self._on_dashboard_rescan_failed)
        rescan_worker.finished.connect(rescan_thread.quit)
        rescan_worker.failed.connect(rescan_thread.quit)
        rescan_thread.finished.connect(rescan_worker.deleteLater)
        rescan_thread.finished.connect(rescan_thread.deleteLater)
        rescan_thread.finished.connect(self._on_dashboard_rescan_thread_finished)
        runtime["dashboard_rescan_thread"] = rescan_thread
        runtime["dashboard_rescan_worker"] = rescan_worker
        rescan_thread.start()

    @Slot(dict)
    def _on_dashboard_rescan_result(self, sections: dict) -> None:
        """Merge fresh fix sections into preloaded_specs and repopulate the cards
        for the sections that were actually re-collected.

        Mirrors ``_on_refresh_result`` (monitor) for every fix card, using the
        same ``set_*`` / ``analyze_*`` calls the startup wiring in app.py uses, so
        the Dashboard and the optimization flow always derive from one source.
        Only cards whose section key is present in ``sections`` are touched -- a
        scoped re-collect leaves the other cards alone, and a failed/empty
        collector for an unscoped section can't clobber a good card. Each card is
        guarded independently so one failure can't strand the rest.
        """
        main = self._main
        runtime = self._runtime
        specs = runtime.get("preloaded_specs", {}) or {}
        specs.update(sections)
        runtime["preloaded_specs"] = specs

        # Monitor (display) card.
        if "DisplayCapabilities" in sections:
            try:
                main._dashboard.set_monitor_data(specs.get("DisplayCapabilities", []) or [])
            except Exception as exc:
                self._log.warning("Monitor card rescan failed: %s", exc, exc_info=True)
        # HDR card (detection-only) -- re-sync alongside display changes.
        if "HDRStatus" in sections:
            try:
                main._dashboard.set_hdr_data(specs)
            except Exception as exc:
                self._log.warning("HDR card rescan failed: %s", exc, exc_info=True)
        # NVIDIA: re-show/hide cards + DLSS recommendation, then per-setting findings.
        if "NVIDIA" in sections:
            try:
                from src.agent_tools.nvidia_profile import analyze_nvidia_profile
                main._dashboard.set_nvidia_data(specs.get("NVIDIA", []))
                main._dashboard.set_nvidia_profile_findings(analyze_nvidia_profile(specs))
            except Exception as exc:
                self._log.warning("NVIDIA card rescan failed: %s", exc, exc_info=True)
        # Power Plan card.
        if "PowerPlan" in sections:
            try:
                from src.agent_tools.power_plan import analyze_power_plan
                main._dashboard.set_power_plan_data(specs.get("PowerPlan"))
                main._dashboard.set_power_plan_findings(analyze_power_plan(specs))
            except Exception as exc:
                self._log.warning("Power Plan card rescan failed: %s", exc, exc_info=True)
        # Game Mode card.
        if "GameMode" in sections:
            try:
                from src.agent_tools.game_mode import analyze_game_mode
                main._dashboard.set_game_mode_data(specs.get("GameMode"))
                main._dashboard.set_game_mode_findings(analyze_game_mode(specs))
            except Exception as exc:
                self._log.warning("Game Mode card rescan failed: %s", exc, exc_info=True)
        # HAGS card.
        if "HAGS" in sections:
            try:
                from src.agent_tools.hags import analyze_hags
                main._dashboard.set_hags_data(specs.get("HAGS"))
                main._dashboard.set_hags_findings(analyze_hags(specs))
            except Exception as exc:
                self._log.warning("HAGS card rescan failed: %s", exc, exc_info=True)

    @Slot(str)
    def _on_dashboard_rescan_failed(self, exc_str: str) -> None:
        self._log.warning("Could not rescan dashboard fix cards: %s", exc_str)

    @Slot()
    def _on_dashboard_rescan_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("dashboard_rescan_thread", None)
        runtime.pop("dashboard_rescan_worker", None)

    def _on_refresh_result(self, displays: list) -> None:
        main = self._main
        runtime = self._runtime
        main._dashboard.set_monitor_data(displays)
        sp = runtime.get("preloaded_specs", {}) or {}
        sp["DisplayCapabilities"] = displays
        runtime["preloaded_specs"] = sp

    def _on_refresh_failed(self, exc_str: str) -> None:
        self._log.warning("Could not refresh monitor card: %s", exc_str)

    @Slot()
    def _on_refresh_thread_finished(self) -> None:
        runtime = self._runtime
        runtime.pop("monitor_refresh_thread", None)
        runtime.pop("monitor_refresh_worker", None)
