"""Orchestrator step / completion wiring, extracted from StartupCoordinator.

A mixin folded into ``StartupCoordinator``. ``on_step`` / ``on_lhm_ready`` /
``on_finished`` are the one-shot handlers ``app.run()`` connects to the
``StartupOrchestrator`` signals; ``on_finished`` does the bulk of the post-startup
dashboard wiring (late-fire path) and seeds the Applied Fixes card. The methods
call sibling handlers (``on_*_fix_requested``, ``refresh_monitor_card``,
``_reload_last_run``) that resolve via the composed coordinator's MRO. No
``__init__``; all state is set by ``StartupCoordinator.__init__``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


class StartupWiringMixin:
    """StartupOrchestrator step/lhm-ready/finished handlers."""

    if TYPE_CHECKING:
        # Provided by StartupCoordinator.__init__ (mixin; declared for the type
        # checker only -- no runtime effect).
        _main: Any
        _runtime: dict
        _log: Any
        _orchestrator: Any
        _pipeline: Any

        # Sibling handlers, resolved via the composed coordinator's MRO.
        def on_thermal_retry_requested(self) -> None: ...
        def on_monitor_fix_requested(self, device: str) -> None: ...
        def refresh_monitor_card(self) -> None: ...
        def on_nvidia_fix_requested(self, check_name: str) -> None: ...
        def on_power_plan_fix_requested(self) -> None: ...
        def on_game_mode_fix_requested(self) -> None: ...
        def on_hags_fix_requested(self) -> None: ...
        def _reload_last_run(self) -> None: ...

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

        # Specs were loaded by StartupOrchestrator Step 3 on the worker
        # thread (see startup.py); reading the attribute here is just a
        # dict reference -- no main-thread file I/O.
        runtime["preloaded_specs"] = getattr(self._orchestrator, "preloaded_specs", {}) or {}

        # Wire the Dashboard Retry button once. on_finished fires exactly once
        # per session, and the button isn't clickable until the dashboard shows
        # (after this), so connecting here is race-free.
        if not runtime.get("_thermal_retry_wired", False):
            try:
                main._dashboard.thermal_retry_requested.connect(self.on_thermal_retry_requested)
                runtime["_thermal_retry_wired"] = True
            except Exception as exc:
                log.warning("Could not wire thermal retry button: %s", exc, exc_info=True)

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

            # Surface the thermal failure cause on the card. The orchestrator
            # records lhm_failure_reason for BOTH a failed start() (startup_lhm
            # is None) AND the running-but-no-sensors PawnIO case (startup_lhm is
            # the live instance) -- so key off the reason, not just None. The
            # Retry button is shown only on failure and stays hidden when thermal
            # monitoring is healthy.
            reason = getattr(self._orchestrator, "lhm_failure_reason", "") or ""
            if reason:
                main._dashboard.thermal_chart.set_offline(reason)
                main._dashboard.set_thermal_retry_visible(True)
            elif startup_lhm is None:
                main._dashboard.thermal_chart.set_offline("Thermal monitor unavailable")
                main._dashboard.set_thermal_retry_visible(True)
            else:
                main._dashboard.set_thermal_retry_visible(False)
        except Exception as exc:
            log.error("on_finished EXC: %s: %r", type(exc).__name__, exc, exc_info=True)

        # Late-fire monitor + NVIDIA card wiring: if main.show() already ran
        # before this slot fired (slow-path on iGPU machines), wire here. The
        # post-splash block in run() wires on the fast-path. _monitor_wired
        # prevents double-wire (both monitor and NVIDIA cards wire together).
        if main.isVisible() and not runtime.get("_monitor_wired", False):
            try:
                _specs = runtime.get("preloaded_specs", {}) or {}
                main._dashboard.set_monitor_data(_specs.get("DisplayCapabilities", []))
                main._dashboard.set_hdr_data(_specs)
                main._dashboard.monitor_fix_requested.connect(self.on_monitor_fix_requested)
                main._dashboard.monitor_refresh_requested.connect(self.refresh_monitor_card)
                main._dashboard.seed_dlss_priority(_specs)
                main._dashboard.set_nvidia_data(_specs.get("NVIDIA", []))
                # Findings parity with the fast path (app.py run()) -- without
                # this, slow-path machines never got the NVIDIA WARNING/OK text.
                from src.agent_tools.nvidia_profile import analyze_nvidia_profile
                main._dashboard.set_nvidia_profile_findings(analyze_nvidia_profile(_specs))
                main._dashboard.nvidia_fix_requested.connect(self.on_nvidia_fix_requested)
                from src.agent_tools.game_mode import analyze_game_mode
                from src.agent_tools.hags import analyze_hags
                from src.agent_tools.power_plan import analyze_power_plan
                main._dashboard.set_power_plan_data(_specs.get("PowerPlan"))
                main._dashboard.set_game_mode_data(_specs.get("GameMode"))
                main._dashboard.set_hags_data(_specs.get("HAGS"))
                main._dashboard.set_power_plan_findings(analyze_power_plan(_specs))
                main._dashboard.set_game_mode_findings(analyze_game_mode(_specs))
                main._dashboard.set_hags_findings(analyze_hags(_specs))
                main._dashboard.power_plan_fix_requested.connect(self.on_power_plan_fix_requested)
                main._dashboard.game_mode_fix_requested.connect(self.on_game_mode_fix_requested)
                main._dashboard.hags_fix_requested.connect(self.on_hags_fix_requested)
                runtime["_monitor_wired"] = True
                log.info("GUI Startup: monitor + NVIDIA + power/game cards wired (late-fire path)")
            except Exception as exc:
                log.warning("Could not wire monitor/NVIDIA cards (late path): %s", exc, exc_info=True)

        # Seed the Applied Fixes card (T-016). on_finished fires exactly once per
        # session on both the fast and slow startup paths, so seeding here covers
        # both without editing app.run(). The card is pre-allocated in
        # RevertView.__init__; the QFileSystemWatcher keeps it fresh thereafter.
        # Reuses _reload_last_run -- the same load_manifest + set_last_run path.
        self._reload_last_run()

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
