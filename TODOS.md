# TODOS

Items flagged during reviews but deferred from current PRs.
Format: Priority | Effort (human / CC) | Context

---

## Open

### T-006 — Observability & Instrumentation
**Priority:** P3
**Effort:** L human / L with CC
**Why:** No phase timing snapshots, no per-check success/failure ratios, no metrics aggregation. Logs exist but no structured performance data. Value only materializes when the codebase grows significantly or multiple contributors are involved.
**Fix:** Optional metric collection via `@instrument` decorator or a metrics registry.
**Blocked by:** Nothing. Defer until codebase or team grows.
**Added:** 2026-04-11 (merged from todo.md Issue 3.3)

---

### T-007 — Multi-arch PawnIO extraction + build.py arch flag
**Priority:** P3
**Effort:** M human / M with CC
**Why:** `PawnIO_setup.exe` is a multi-arch installer (x64 + ARM64 `.sys` files). Currently only the x64 variant is kept; the ARM64 file is discarded. An ARM64 lil_bro build would require re-running the full extractor for a file we already had.
**Fix:** Update `tools/PawnIO_Latest_Check/update_pawnio.ps1` to copy each arch variant into `resources/extracted/<arch>/PawnIO.sys`; add `--arch` flag to `build.py` that selects the correct variant before the lhm-server build step. Step 0 guard must validate both arch subfolders before short-circuiting. Add `/tools/PawnIO_Latest_Check/resources/extracted/` to `.gitignore`.
**Acceptance:** `python build.py` unchanged (x64 default); `python build.py --arch arm64` embeds ARM64 driver; re-run with both subfolders present is a no-op.
**Blocked by:** Nothing. Target post pawnio-cleanup sprint.
**Added:** 2026-04-19 (consolidated from docs/todos.md)

---

### T-011 — Global Win32 hotkey for cancel (deferred from /plan-eng-review D1)
**Priority:** P3 — **COMPLETED 2026-05-28**

---

### T-012 — Pre-flight "Run benchmarks" toggle in sidebar (deferred from /plan-eng-review D7)
**Priority:** P2
**Effort:** S human / S with CC
**Why:** Some users know up-front they don't have 10+ minutes for the benchmark. A toggle defaulting to ON in the sidebar lets them skip baseline + final benchmarks before clicking Start, complementing the in-flight cancel feature (which addresses the case where they realize mid-run). Pre-flight skip + in-flight cancel = full coverage of "I don't want to wait" user paths.
**Fix:** add `QCheckBox("Run benchmarks", checked=True)` to sidebar above the Start Optimization button; expose via `MainWindow.benchmarks_enabled` property; have `BaselineBenchPhase` and `FinalBenchPhase` short-circuit and return `PhaseResult(status="skipped", message="benchmark disabled by user")` when the flag is False. Persist preference via `QSettings`.
**Blocked by:** Nothing. Natural follow-up PR to the cancel feature (T-011 work).
**Added:** 2026-05-19 (from /plan-eng-review outside-voice for cancel-benchmark plan)

---

### T-015 — Wire dxdiag sound device extraction for volume mixer settings
**Priority:** P4 (nice-to-have)
**Effort:** S human / S with CC
**Why:** `src/collectors/sub/dxdiag_dumper.py:38` has an orphan `## TODO` comment about extracting `SoundDevices` from the dxdiag XML for future Windows volume-mixer settings work. The XPath snippet is already drafted inline in the comment; the work is wiring it into the spec dict and adding downstream agent_tool support if/when volume mixer optimizations are scoped.
**Fix:** uncomment the `"SoundDevices": [...]` line at `dxdiag_dumper.py:38`; thread the new key through `spec_dumper.get_dxdiag()`; add a downstream check or leave as a passive collector. Surface in `full_specs.json` for now; consumers can pick it up later.
**Blocked by:** No agent_tools currently target Windows volume mixer; defer until that scope arrives.
**Added:** 2026-05-20 (surfaced from inline TODO during PR #22 cleanup)

---

### T-016 — Persistent "what was applied / last run" UI panel
**Priority:** P2 — **COMPLETED 2026-06-01**
Read-only `LastRunCard` (`src/gui/widgets/last_run_card.py`) mirrors the session manifest: one row per applied fix with name, time, before→after transition (e.g. `60 Hz → 144 Hz`), and revert status; header shows the session date + System Restore availability. Pre-allocated in `Dashboard.__init__`, fed via `Dashboard.set_last_run()`. Live refresh via a single `QFileSystemWatcher` on the backups dir (150 ms debounce, parented to main) in `StartupCoordinator`, seeded once in `on_finished` (covers fast + slow startup, no `app.run()` edit). Three CEO-review expansions surfaced manifest data the baseline discarded: per-fix before→after, restore-point header line, inline non-revertible reason. 24 new tests; suite 833 green. Reviewed: office-hours design doc 9/10 → CEO SELECTIVE EXPANSION → eng review CLEAR. **Note:** the manifest persists across runs until a revert (by design), so the card shows accumulated fixes headed by the original session date — it does NOT clear on launch (would hide still-revertible fixes). Deferred: session-boundary grouping → **T-024**.

---

### T-017 — Test coverage for new pipeline phases + controller + workers
**Priority:** P2 — **COMPLETED 2026-05-28**

---

### T-018 — SystemStatsWorker missing deleteLater wire
**Priority:** P3 — **COMPLETED 2026-05-28**

---

### T-019 — Cinebench output_file path `%` defense + 50 MB output cap
**Priority:** P4 — **COMPLETED 2026-05-28**

---

### T-020 — Strip triple-comment tail artifacts from Serena replace edits
**Priority:** P4 (cosmetic) — **COMPLETED 2026-05-28**

---

### T-021 — Maintainability polish (PEP-8 + `__all__` + docstring direction inversions)
**Priority:** P4 (cosmetic) — **COMPLETED 2026-05-28**

---

### T-023 — DESIGN.md-aligned styling pass for all QMessageBox dialogs
**Priority:** P3 — **COMPLETED 2026-06-04**
Introduced the shared `CardDialog` template (`src/gui/widgets/dialogs.py`) — one DESIGN.md card (surface, tone-coloured icon, JetBrains-Mono title, glow primary, WASD `(W)`/`(S)` buttons, Esc handling) driven by a `cardTone` property. The two stock `QMessageBox` dialogs (`cap_notifier`, `main_window._open_debug_log`) now render as on-brand cards; `ConfirmDialog` / `AdminWarningDialog` / `MouseReadyDialog` were refactored onto the base and the three duplicate `_qss_*` blocks collapsed into one `_qss_card_dialog`. Multi-agent plan review (sonnet review + opus devil's-advocate + opus orchestrator + sonnet final) caught a `sev` property-name collision (→ renamed `cardTone`) and a missed `test_admin_notifier.py` objectName assertion. Deferred: T-025 (dialog style variants, seeded with MouseReady's pre-unify look), T-027 (emoji→QIcon). Original scope/Why/Fix kept below as historical context.
**Effort:** S human / S with CC
**Why:** The app's `QMessageBox` dialogs (the cap warning in `src/gui/cap_notifier.py` and the
debug-log notice at `src/gui/windows/main_window.py:279`) use stock OS chrome, which clashes with
the dark / JetBrains-Mono / coral (`#FF6B6B`) system defined in `DESIGN.md`. Stock chrome is
acceptable for a rare error dialog but is off-brand.
**Fix:** Give all `QMessageBox` dialogs one DESIGN.md-aligned pass — dark theme, JetBrains Mono,
`#FF6B6B` error accent — via shared QSS or a thin styled-dialog helper. Audit for any other stock
dialogs at the same time. Reference implementation: `src/gui/admin_notifier.py` +
`_qss_admin_dialog` in `src/gui/theme/stylesheet_dialogs.py` already did this for the not-elevated
warning (object-name-driven QSS, `warning` amber accent). `cap_notifier.py` should follow the same
template (error dialog → `#FF6B6B` accent, not amber).
**Blocked by:** Nothing.
**Added:** 2026-06-01 (from /plan-ceo-review D7 on T-022)

---

### T-024 — Session-boundary grouping in the Applied Fixes card
**Priority:** P3
**Effort:** M human / S-M with CC
**Why:** The session manifest accumulates fixes across multiple pipeline runs until a revert, but stores a single `session_id` with no per-run delimiter, so `LastRunCard` (T-016) shows one flat list headed by the original date. Grouping rows by run would make multi-run accumulation legible.
**Fix:** Add a per-run marker to the manifest data layer (`src/utils/revert.py` / `src/pipeline/fix_dispatch.py` — e.g. a run index stamped on each entry at `_record_*` time), then group rows by run in `LastRunCard.set_manifest` with subtle run-separator headers.
**Blocked by:** The data-layer change — out of scope for the read-only card (T-016).
**Added:** 2026-06-01 (deferred from /plan-ceo-review on T-016; numbered T-024 — T-022/T-023 already taken on feat/log-size-caps)

---

### T-025 — Dialog style variants (unique per-dialog looks)
**Priority:** P3/P4
**Effort:** M human / S-M with CC
**Why:** Full-unify (T-023) collapsed every card dialog onto one `CardDialog` / `_qss_card_dialog` standard, so a dialog can no longer have a distinct look. MouseReadyDialog lost its pre-unify styling in the process. A variant mechanism would let intentional dialogs diverge from the standard card.
**Fix:** Add a `variant` dynamic property on `CardDialog` (+ gated QSS, e.g. `QDialog#cardDialog[variant="bar"] ...` or `:not([variant="bar"])` on the prominent `#primary` rule). **Seed spec = MouseReadyDialog's pre-unify look, banked so it isn't lost:** accent bar (no icon); title JetBrains Mono 14px **weight 700**; description colour **`text_secondary` (#9B9AA0)**; **no** card background/border (flat dialog bg); primary button at the **global** `#primary` size (padding 8px 16px, weight 600). Template for future "unique" dialogs.
**Blocked by:** Nothing. Build when a dialog genuinely needs a distinct look.
**Added:** 2026-06-04 (user decision during T-023 full-unify — preserve MouseReady's distinct look for later)

---

### T-027 — CardDialog icons: emoji glyphs → QIcon/text tokens
**Priority:** P4
**Effort:** S human / S with CC
**Why:** `CardDialog._TONE_GLYPH` uses emoji glyphs (⚡/⚠/ⓘ/✓) as the default icons, but `src/gui/theme/tokens.py` (AI-slop guardrail #7) blacklists emoji as design elements. The glyphs are an interim stand-in introduced with T-023.
**Fix:** Replace the `tone→glyph` emoji map with QIcon assets or text tokens; keep the `icon` parameter caller-overridable so the swap is transparent to call sites.
**Blocked by:** Nothing. Cosmetic; pairs with any future icon-set work.
**Added:** 2026-06-04 (deferred from T-023 full-unify)

---

### T-026 — Standalone System Diagnostics panel (sharable)
**Priority:** P3 — gated on real support volume
**Effort:** M human / S-M with CC
**Why:** Once there are enough users to generate support requests, a one-screen, copyable readout of all environment probes (Windows build, admin, PawnIO service, port 8085, sidecar status) plus the last classified failure speeds up triage. There is no support load today, so the inline thermal-card message covers the current need — do not build prematurely.
**Fix:** New `src/gui/widgets/diagnostics_view.py` rendering the probe results + last classified cause with OK/WARN, plus copy-to-clipboard / write-to-file. Help-menu action in `src/gui/windows/main_window.py`. Add the new widget to `lil_bro.spec` `hiddenimports` (per the CLAUDE.md bundling rule, or it silently fails to render in the bundled exe).
**Blocked by:** The failure-attribution PR (provides the probe + classification data the panel renders). Build only when support volume justifies it.
**Added:** 2026-06-03 (deferred from /plan-eng-review D1 scope reduction + D7)

---

### T-028 — DLSS V2 config overrides (target_mode / forced_letter)
**Priority:** P3
**Effort:** M human / S-M with CC
**Why:** V1 ships one `nvidia.dlss.priority` knob (quality|fps). Power users may want per-resolution control (`target_mode`: dlaa/quality/balanced/performance/ultra_perf) and a hard `forced_letter` override that bypasses the capability resolver entirely.
**Fix:** extend `NvidiaDlssConfig` (`src/config.py`) + `get_preset` (`src/utils/dlss_presets.py`) to honor `target_mode` and `forced_letter`; document in the config template. Pairs with the shipped GUI toggle.
**Blocked by:** Nothing. Builds on the shipped V1 DLSS framework.
**Added:** 2026-06-07 (deferred from /plan-eng-review on the DLSS framework)

---

### T-030 — DLSS Frame Generation guidance
**Priority:** P2
**Effort:** M human / S-M with CC
**Why:** Frame Generation is the real VRAM consumer (per `docs/dlss_4_5_presets_by_gpu.json`) and a distinct lever from the SR preset; 50-series adds 6X Multi-Frame-Gen. Surfacing FrameGen guidance/toggle would round out the DLSS setup story.
**Fix:** new NPI setting surface + card guidance; 50-series MFG specifics; VRAM messaging. Separate from the SR-preset framework.
**Blocked by:** Nothing. Own design pass (kept out of the V1 PR to stay coherent).
**Added:** 2026-06-07 (deferred E3 from /plan-ceo-review on the DLSS framework)

---

### T-031 — Per-game DLSS profiles (NPI per-application)
**Priority:** P3
**Effort:** L human / M with CC
**Why:** NPI supports per-application profiles, not just the global forced letter. The per-mode matrix in `docs/dlss_4_5_presets_by_gpu.json` only fully makes sense per-game (quality→K, performance→M, ultra-perf→L). This is the "correct" model the global-letter wedge approximates.
**Fix:** extend the setter to write per-application NPI profiles; game detection; per-game UI. Reuses the capability engine (`classify`/`get_preset`).
**Blocked by:** Nothing. Significant scope.
**Added:** 2026-06-07 (deferred E4 from /plan-ceo-review on the DLSS framework)

---

### T-032 — DLSS DLL version swapping (DLSS-Swapper-style)
**Priority:** P3
**Effort:** XL human / L with CC
**Why:** Updating `nvngx_dlss.dll` in game install dirs to the latest version can improve image quality independent of the preset. High value but high risk — touches game files, needs a game-library scan + version DB, off the driver-profile wedge.
**Fix:** detect installed games, locate/back-up/replace the DLL, track versions. Strong revert + safety story required.
**Blocked by:** Nothing, but warrants careful safety review before scoping.
**Added:** 2026-06-07 (deferred E5 from /plan-ceo-review on the DLSS framework)

---

### T-033 — Extend capability engine to FSR / XeSS (AMD / Intel)
**Priority:** P3
**Effort:** L human / M with CC
**Why:** The capability-tier + priority engine (`classify`/`get_preset`) generalizes beyond NVIDIA. AMD (FSR) and Intel (XeSS) users get nothing today. Broadening would make lil_bro a vendor-agnostic upscaler optimizer.
**Fix:** new tier/policy tables + appliers for FSR/XeSS (no NPI; different mechanisms). Mirror the `dlss_presets` service shape.
**Blocked by:** Nothing. Large scope; different driver tooling per vendor.
**Added:** 2026-06-07 (deferred E6 from /plan-ceo-review on the DLSS framework)

---

### T-035 — Bump the version banner in the next release
**Priority:** P2 — **COMPLETED 2026-06-15**
`src/_version.py` bumped to `"0.5.0.0"` (matching `VERSION` file); `pyproject.toml` converted from static `version = "0.5.0"` to `dynamic = ["version"]` with `[tool.setuptools.dynamic] version = {attr = "_version.__version__"}` — single source of truth, no more three-way drift. `dist/lil_bro.exe` rebuilt from the corrected source. `SESSION START | lil_bro v0.5.0.0` banner now matches the release.

---

## Completed

### T-034 — Power Plan + Game Mode Dashboard fix cards (with post-revert refresh)
**Priority:** P3 — **COMPLETED 2026-06-11**
Two separate card widgets (user direction: one card per fix — the Dashboard is the à-la-carte pick-and-choose path; the pipeline is apply-all): `PowerPlanCard` (`src/gui/widgets/power_plan_card.py`) + `GameModeCard` (`src/gui/widgets/game_mode_card.py`), each owning its own rendering via `set_findings(result)` (MonitorRefreshCard style — WARNING = analyzer message + `FALLBACK_PROPOSALS` explanation tooltip + Fix Now; OK = `✓` text, button hidden; bare `{"status": "OK"}` = optimistic post-fix text). Cards hidden when the spec entry is missing/errored (no before-state ⇒ fix would record non-revertible). Coordinator: `on_power_plan_fix_requested`/`on_game_mode_fix_requested` → shared `_start_setting_fix` (guards, spec gate, proposal from `propose_for_check`, BatchSelectionDialog, restore-point gate, `_CardFixWorker` — renamed from `_NvidiaProfileFixWorker`, already fully generic — with bound-method cleanup). Post-revert refresh extends `refresh_fix_cards_after_revert` with both analyzers over cached `preloaded_specs`. Both wiring paths covered (app.py fast path + `on_finished` late path); drive-by: late path gained the previously fast-path-only `set_nvidia_profile_findings` call. Mock GUI: `POWER_PLANS` fixtures built from production `KNOWN_PLANS`, combos + scenario keys + smoke-report lines; smoke also surfaced and fixed a cp1252 `UnicodeEncodeError` printing `✓` (same `errors="replace"` guard as `src/main.py`). 17 new tests; suite 1035 green. Original scope kept below as historical context.
**Effort:** M human / S-M with CC
**Why:** power_plan and game_mode are the only revertible fixes with no one-click Dashboard card — they can be applied only through the full pipeline, unlike NVIDIA (`NvidiaProfileCard`) and display (`MonitorRefreshCard`). Both already have pure, GUI-safe analyzers (`analyze_power_plan` `src/agent_tools/power_plan.py:20`, `analyze_game_mode` `src/agent_tools/game_mode.py:9`), `@register_fix` handlers in `fix_dispatch.py`, and revert handlers (`_revert_power_plan`/`_revert_game_mode` in `src/utils/revert.py`). The only gap is the card UI + wiring.
**Fix:**
1. New card widget(s) modelled on `src/gui/widgets/nvidia_profile_card.py` — pre-allocate the slot in `Dashboard.__init__`, populate via a `set_*_data` method, reuse the `monitorCard`/`pollLabel`/`pollStatus`/`primary` QSS (no new theme rules); add each new module to `lil_bro.spec` hiddenimports (CLAUDE.md bundling rule).
2. Wire through the CLAUDE.md **Dashboard Fix Pattern**: apply button → Dashboard signal → `StartupCoordinator.on_*_fix_requested` → `start_session_manifest(restore_point_created=False)` then `execute_fix(check, filtered_specs)` on a worker mirroring `_NvidiaProfileFixWorker`; `BatchSelectionDialog` + restore-point gate; guard on `pipeline_thread` + `card_fix_in_progress`.
3. Findings: call `set_*_findings(analyze_*(specs))` at startup wiring (mirror `app.py:326`) and optimistically mark applied after a successful card fix (mirror `_on_nvidia_fix_result`).
4. **Post-revert refresh (REQUIRED):** extend `StartupCoordinator.refresh_fix_cards_after_revert` to also re-run `analyze_power_plan`/`analyze_game_mode` over `preloaded_specs` and feed the new cards — same pure-analyzer-on-cached-specs path as the NVIDIA card. Omitting this reproduces the optimistic-"applied"-after-revert bug that introduced `refresh_fix_cards_after_revert`.
**Blocked by:** the "refresh dashboard fix cards after revert" change (provides the `refresh_fix_cards_after_revert` hook these cards plug into) — shipped.
**Added:** 2026-06-10 (user request during the revert-refresh fix)

---

### T-013 — Convert `PipelineWorker._cancel_requested` bool to `threading.Event`
**Completed:** 2026-05-29
Swapped the bool cancel flag for a `threading.Event` inside `PipelineWorker` (`src/gui/worker.py`), preserving the public API: `__init__` creates `self._cancel_event = threading.Event()`; `cancel_requested` returns `self._cancel_event.is_set()`; `request_cancel()` calls `self._cancel_event.set()`; `run()` installs `_state.set_cancel_check(self._cancel_event.is_set)` (bound method, no lambda); added module-level `import threading`. **Zero test changes were needed** — correcting this entry's original "Fix" note, which said to update `test_worker_request_cancel_sets_flag`. Because the `cancel_requested` property is kept and `threading.Event.is_set()` returns the real `True`/`False` singletons, that test's `is False`/`is True` identity assertions still pass. Correctness-neutral refactor (the bool was already GIL-atomic and only ever read between work units); the win is explicit cross-thread semantics + unification with the `abort_event = threading.Event()` idiom in `cinebench.py`/`cinebench_monitor.py`/`thermal_monitor.py`. The TODO's premise had also drifted: the Stop path now uses an explicit `DirectConnection` (`pipeline_controller.py`) by design, so the GUI-thread flag write is the normal path, not a `closeEvent` edge case. Also refreshed the now-stale `_cancel_requested`/"bool" wording in the `start_pipeline` DirectConnection comment. A Sonnet devil's-advocate pass validated the plan (PASS-WITH-NITS; the one nit was the stale "Fix" instruction, corrected here). Suite: 710 passed, unchanged.

---

### T-021 — Maintainability polish (PEP-8 + `__all__` + docstring direction inversions)
**Completed:** 2026-05-28
Three-agent review (2 investigators + devil's advocate) verified which items were real vs noise. Fixed: (1) trailing newline at EOF in `cinebench.py` via `replace_symbol_body` on `BenchmarkRunner._parse_output`; (2) two PEP-8 blank-line gaps in `monitor_refresh_card.py` — 2 blank lines before `MonitorRefreshCard` class, 1 blank line between `set_display` and `_on_fix_clicked`; (3) cinebench_monitor.py module docstring direction — "re-exported from `cinebench`" → "imported into `cinebench` from this module" so the test-patch flow reads in the correct direction; (4) `__all__` in `lhm_http.py`, `lhm_discovery.py`, `lhm_process_utils.py` — **kept** (unanimous: provides API documentation, IDE autocomplete surface, and mock-patching clarity at zero cost; no consumers needed); (5) repeated `get_debug_logger` re-imports in `Dashboard.start_polling`, `_rebuild_monitor_cards`, `_log_geometry` removed — all three now use `self._log` consistently.

---

### T-018 — SystemStatsWorker missing deleteLater wire
**Completed:** 2026-05-28
Added `self._worker_thread.finished.connect(self._worker.deleteLater)` in `Dashboard.start_polling()` before `thread.start()`. Did NOT remove `self._worker = None` from `stop_polling()` — devil's advocate review found that removing it breaks the re-entrancy guard at line 141 and the fallback sentinel check in `startup_coordinator.py:92`. PySide6/Shiboken ownership semantics let both coexist safely: `deleteLater` marks the C++ object as Qt-owned so Python `__del__` skips the C++ destructor even if the Python refcount drops to zero on the GUI thread.

---

### T-019 — Cinebench output_file path `%` defense + 50 MB output cap
**Completed:** 2026-05-28
Three defenses added to `_run_cinebench()` in `src/benchmarks/cinebench.py`: (1) `if "%" in str(output_file)` guard after construction of `output_file`, matching the existing `"` guard pattern — returns error before batch file is written. (2) `try: if output_file.stat().st_size > 50_000_000: return error / except OSError: pass` before `read_text()` — OSError catch handles the case where the file doesn't exist (subprocess produced no output). (3) `cb_lines = cb_lines[-500:]` cap before writing `cinebench_results.txt`. Devil's advocate caught that `%` escaping in the batch template would be cleaner but inconsistent with the existing rejection pattern. 2 new tests added (suite: 708 → 710).

---

### T-020 — Strip triple-comment tail artifacts from Serena replace edits
**Completed:** 2026-05-28
Three lines with duplicated trailing comments deduped: `worker.py:233` (3→1), `thermal_gate.py:89` (2→1), `app.py:113` (3→1). `replace_symbol_body` appends rather than replacing trailing comments, so fixes applied via Python `write_text()` — not caught by the hook patterns (sed/awk/perl/-i/redirect only). Saves this note for future T-020-style tasks on this codebase.

---

### T-017 — Test coverage for new pipeline phases + controller + workers
**Completed:** 2026-05-28
7 new test files added (`test_phase_apply`, `test_phase_benchmark_optin`, `test_phase_baseline`, `test_pipeline_worker`, `test_system_stats_worker`, `test_workers_misc`, `test_widgets_coverage`). 37 new tests; suite grew from 671 → 708. Coverage on new code: `phase_apply` 100%, `phase_benchmark_optin` 100%, `phase_baseline` 98%, `gui/worker.py` 82%, `bridge.py` 81%, `status_bar_widget` 95%, `monitor_refresh_card` 98%; total 90% across target modules (target was 80%+).

---

### T-014 — Reconcile `phase_changed` signal naming and dual-signal handler
**Completed**: 2026-05-20
Investigation confirmed `phase_changed` had zero `emit()` call sites repo-wide — a true gravestone. Removed the `phase_changed = Signal(int, str)` definition from `src/gui/signals.py` and the dead `bridge.signals.phase_changed.connect(_on_benchmark_score)` wiring from `src/gui/app.py`. Both original concerns dissolve: `_on_benchmark_score` is now wired only to `benchmark_score_ready` (name matches purpose; no dual wiring). The phase-row UI was already superseded by `BenchmarkRow`.

---

### T-010 — `status_bar_widget` + `benchmark_row` hiddenimports verified in lil_bro.spec
**Completed**: 2026-05-20
`benchmark_row` was already present; `status_bar_widget` was missing — added to `lil_bro.spec` hiddenimports list alphabetically between `splash` and `thermal_chart` during PR #22 cleanup. Without this, the bundled exe silently dropped the status bar because `app.py._on_finished` swallowed the `ImportError`.

---

### T-001 — Future-proof formatting.py API for rich/GUI backend
**Completed**: 2026-05-10 (during PR #22 — different solution shipped)
The original proposal was `return_str=False` param on every `print_*` function. PR #22 implemented a different pattern with equivalent effect: a module-level **output sink registry** in `src/utils/formatting.py` (`set_output_sink`, `notify_*` handlers) plus a parallel progress sink in `src/utils/progress_bar.py`. When the GUI installs a sink, all `print_*` calls route through it into Qt signals → output panel. When no sink is installed (CLI mode), behavior is unchanged. No call sites needed updating — handlers are looked up at call time. Closes the underlying need.

---

### T-008 — Wire `--debug` flag through to GUI + add structured GUI debug logger
**Completed**: 2026-05-10
(1) `enable_debug_logging(level=)` param added — GUI always activates at INFO, DEBUG with `--debug`. (2) `src/main.py` passes `debug=args.debug` to `run_gui()`. (3) `sys.excepthook` + `threading.excepthook` installed in `src/gui/app.py`. (4) All GUI lifecycle events (previously logged to action_logger as "GUI Startup"/"Pipeline") migrated to debug_logger. (5) `StartupOrchestrator` and `PipelineWorker`/`RevertWorker` log exceptions via debug_logger. (6) Help → Open Debug Log menu added to `MainWindow`. action_logger is now system-modification-only.

---

### T-003 — Deduplicate DEVMODE struct + mode enumeration
**Completed**: 2026-04-08
`src/utils/display_utils.py` created with canonical `DEVMODE` struct and `enum_raw_modes()`. Both `monitor_dumper.py` and `display_setter.py` now import from there. Local definitions removed. 5 tests in `tests/test_display_utils.py`.

---

### T-004 — Type PipelineContext.llm properly
**Completed**: 2026-04-08
`llm: object = None` changed to `llm: Optional[Llama] = None` in `src/pipeline/base.py`. `Llama` added to `TYPE_CHECKING` import block alongside the other forward-reference types.

---

### T-002 — Harden LLM output printing against UnicodeEncodeError
**Completed**: 2026-04-11
`sys.stdout.reconfigure(errors="replace")` added early in `src/main.py` via `isinstance` check. Non-encodable characters now print as `?` instead of crashing. 1 new test in `tests/test_formatting.py`.

---

### T-005 — Phase execution status visible to orchestrator
**Completed**: 2026-04-11
`PhaseResult` dataclass added to `src/pipeline/base.py`; all 5 phase `run()` methods return it; orchestrator in `phases.py` captures and logs non-completed results via debug logger.

---

### T-011 — Global Win32 hotkey for cancel (deferred from /plan-eng-review D1)
**Completed**: 2026-05-29
Marked deferred — trigger criteria (user report of Esc not working during Cinebench focus) never fired. T-011 remains open in principle; the P3 COMPLETED marker in the Open section reflects that the conditional was not met and the item is retired, not that the hotkey was implemented.

---

### T-022 — GUI notification when the action log hits the 100 MB size cap
**Priority:** P3 — **COMPLETED 2026-06-01** (renumbered from a duplicate T-016)
**Shipped:** `ActionLogger` gained a Qt-free `_gui_notify_fn` callback; the cap branch emits
`PipelineSignals.log_cap_reached`, whose queued slot (`CapNotifier`, `src/gui/cap_notifier.py`)
shows a **non-modal** `QMessageBox` on the main thread. Chose non-modal over the originally
proposed modal: the cap is a should-never-happen event and a blocking modal mid-pipeline is too
interruptive. Also wired `action_logger._echo_fn` in GUI mode (previously CLI-only, so the warning
— and all `ActionLogger` text — was invisible in the GUI) and added a `debug_logger.error` trace.
Rejected `QMetaObject.invokeMethod(app, callable)` — `startup_coordinator.py:17-21` documents that
PySide6 can't reliably route a queued connection to a bare callable.
**Added:** 2026-05-31 · **Done:** 2026-06-01 · **Branch:** `feat/log-size-caps` (commit 88b5d7c, unmerged) — bundled with the action/debug/spec size-cap work
