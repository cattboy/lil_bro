"""Startup orchestration coordinator for the GUI.

Extracted from ``app.run()``'s closure: owns the StartupOrchestrator
step / lhm-ready / finished handlers and the monitor-refresh-card
handlers. ``app.run()`` constructs one instance and routes the
orchestrator + dashboard signals to its methods.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Slot


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


class StartupCoordinator:
    """Owns the StartupOrchestrator + monitor-refresh-card signal handlers.

    Constructed once by ``app.run()``; the shared ``runtime`` dict is stored
    by reference. ``pipeline`` is the PipelineController -- ``on_finished``
    re-enables the flow controls through it once startup completes.
    """

    def __init__(self, main, runtime: dict, log, orchestrator, pipeline) -> None:
        self._main = main
        self._runtime = runtime
        self._log = log
        self._orchestrator = orchestrator
        self._pipeline = pipeline

    # ── Orchestrator step / completion ─────────────────────────────────

    def on_step(self, name: str, status: str) -> None:
        try:
            self._log.debug("GUI Startup step: %s status=%s", name, status)
            label = (
                f"{name}: failed (continuing)"
                if status == "fail"
                else f"{name}…"
            )
            self._main.status_bar_widget.set_state("run", label)
        except Exception as exc:
            self._log.error("on_step EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

    def on_finished(self, startup_lhm) -> None:
        log = self._log
        runtime = self._runtime
        main = self._main
        log.info(
            "GUI Startup: on_finished entry (lhm=%s)",
            "yes" if startup_lhm else "no",
        )
        runtime["startup_done"] = True
        # Idempotent: on_lhm_ready set this earlier in the success path; here
        # it covers the LHM-failed case where on_lhm_ready was never called.
        runtime["lhm"] = startup_lhm

        # Load pre-collected specs (written by StartupOrchestrator Step 3)
        preloaded_specs: dict = {}
        if self._orchestrator.specs_path:
            try:
                import json as _json
                with open(self._orchestrator.specs_path, encoding="utf-8") as _f:
                    preloaded_specs = _json.load(_f)
            except Exception as e:
                log.debug("preloaded specs load failed: %s", e)
        runtime["preloaded_specs"] = preloaded_specs

        try:
            if runtime.get("pipeline_thread") is None and runtime.get("revert_thread") is None:
                self._pipeline.set_flow_controls(True)
        except Exception:
            pass  # safe: flow-control restore is best-effort; runtime keys may be missing during shutdown
        try:
            main.status_bar_widget.set_state("ok", "Idle")

            # Defensive fallback: polling normally starts from on_lhm_ready
            # several seconds earlier. If that QueuedConnection didn't deliver
            # for any reason, on_finished is the safety net. start_polling()
            # guards against double-call internally (returns if _worker is set),
            # so this is harmless when the normal path already fired.
            if startup_lhm is not None and main._dashboard._worker is None:
                log.warning(
                    "GUI Startup: lhm_ready slot never delivered -- "
                    "falling back to start_polling from on_finished"
                )
                main._dashboard.start_polling()

            if startup_lhm is None:
                main._dashboard.thermal_chart.set_offline("Thermal monitor unavailable")
        except Exception as exc:
            log.error("on_finished EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

        # Late-fire monitor wiring: if main.show() already ran before this slot
        # fired (slow-path on iGPU machines), wire here. The post-splash block
        # in run() wires on the fast-path. _monitor_wired prevents double-wire.
        if main.isVisible() and not runtime.get("_monitor_wired", False):
            try:
                _specs = runtime.get("preloaded_specs", {}) or {}
                main._dashboard.set_monitor_data(_specs.get("DisplayCapabilities", []))
                main._dashboard.monitor_fix_requested.connect(self.on_monitor_fix_requested)
                main._dashboard.monitor_refresh_requested.connect(self.refresh_monitor_card)
                runtime["_monitor_wired"] = True
                log.info("GUI Startup: monitor card wired (late-fire path)")
            except Exception as exc:
                log.warning("Could not wire monitor card (late path): %s", exc, exc_info=True)

        log.info("GUI Startup: on_finished exit")

    def on_lhm_ready(self, lhm) -> None:
        """Start dashboard polling the moment LHM is ready (orchestrator Step 1).

        Firing here -- rather than after the whole startup completes -- gives
        the worker ~5-10s of "free" polling time while the splash still shows
        later steps, so cards are populated by splash close.
        """
        log = self._log
        log.info("GUI Startup: lhm_ready received, starting dashboard polling early")
        self._runtime["lhm"] = lhm
        try:
            self._main._dashboard.start_polling()
        except Exception as exc:
            log.error("on_lhm_ready EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

    # ── Monitor refresh card ───────────────────────────────────────────

    def refresh_monitor_card(self) -> None:
        main = self._main
        runtime = self._runtime
        try:
            from src.collectors.sub.monitor_dumper import get_monitor_refresh_capabilities
            displays = get_monitor_refresh_capabilities()
            main._dashboard.set_monitor_data(displays)
            sp = runtime.get("preloaded_specs", {}) or {}
            sp["DisplayCapabilities"] = displays
            runtime["preloaded_specs"] = sp
        except Exception as exc:
            self._log.warning("Could not refresh monitor card: %s", exc)

    def on_monitor_fix_requested(self, device: str) -> None:
        runtime = self._runtime
        main = self._main
        log = self._log
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
        # Filter so _fix_display targets ONLY this device
        filtered_specs = {**specs, "DisplayCapabilities": [target]}
        from src.gui.worker import _MonitorFixWorker
        fix_thread = QThread()
        fix_worker = _MonitorFixWorker(filtered_specs)
        fix_worker.moveToThread(fix_thread)
        fix_thread.started.connect(fix_worker.run)
        fix_worker.finished.connect(fix_thread.quit)
        fix_thread.finished.connect(self.refresh_monitor_card)
        fix_thread.finished.connect(fix_worker.deleteLater)
        fix_thread.finished.connect(fix_thread.deleteLater)
        runtime["monitor_fix_thread"] = fix_thread
        runtime["monitor_fix_worker"] = fix_worker
        fix_thread.finished.connect(lambda: runtime.pop("monitor_fix_thread", None))
        fix_thread.finished.connect(lambda: runtime.pop("monitor_fix_worker", None))
        fix_thread.start()
