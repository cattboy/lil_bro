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
**Priority:** P3 (conditional on observed need)
**Effort:** S human / S with CC
**Why:** Current app-scoped `QShortcut(Qt.WindowShortcut)` for Esc/Q only fires when `MainWindow` is the active window. `_minimize_cinebench_window` minimizes Cinebench at launch so lil_bro returns to the foreground, but if Cinebench re-grabs focus during its 10-minute run, the keyboard cancel path goes silent. The Stop button still works regardless of focus.
**Trigger criteria:** any v1 user reports "I pressed Esc but nothing happened during Cinebench" — verify Cinebench was foreground at the moment.
**Fix:** add `ctypes.windll.user32.RegisterHotKey(MOD_NONE, VK_ESCAPE)` + a message-loop thread that emits `MainWindow.stop_requested` on `WM_HOTKEY`. Unregister in `_on_pipeline_finished`. Same pattern for `VK_Q`. Keep the existing app-scoped QShortcuts as fallback when MainWindow has focus.
**Blocked by:** v1 telemetry / user reports.
**Added:** 2026-05-19 (from /plan-eng-review for cancel-benchmark plan)

---

### T-012 — Pre-flight "Run benchmarks" toggle in sidebar (deferred from /plan-eng-review D7)
**Priority:** P2
**Effort:** S human / S with CC
**Why:** Some users know up-front they don't have 10+ minutes for the benchmark. A toggle defaulting to ON in the sidebar lets them skip baseline + final benchmarks before clicking Start, complementing the in-flight cancel feature (which addresses the case where they realize mid-run). Pre-flight skip + in-flight cancel = full coverage of "I don't want to wait" user paths.
**Fix:** add `QCheckBox("Run benchmarks", checked=True)` to sidebar above the Start Optimization button; expose via `MainWindow.benchmarks_enabled` property; have `BaselineBenchPhase` and `FinalBenchPhase` short-circuit and return `PhaseResult(status="skipped", message="benchmark disabled by user")` when the flag is False. Persist preference via `QSettings`.
**Blocked by:** Nothing. Natural follow-up PR to the cancel feature (T-011 work).
**Added:** 2026-05-19 (from /plan-eng-review outside-voice for cancel-benchmark plan)

---

### T-013 — Convert `PipelineWorker._cancel_requested` bool to `threading.Event`
**Priority:** P3
**Effort:** XS human / XS with CC
**Why:** Outside-voice review flagged that `request_cancel()` is called across thread boundaries — most paths are mediated by Qt's `AutoConnection` (which picks `QueuedConnection` and routes the slot to the worker thread), but `app.py` `closeEvent` calls `request_cancel()` directly from the GUI thread, writing the bool from one thread while the polling code reads it from another. CPython's GIL makes single-bool writes/reads atomic in practice, but `threading.Event` makes the semantics explicit and unifies with the existing `abort_event = threading.Event()` pattern already used inside `cinebench.py`.
**Fix:** replace `self._cancel_requested: bool = False` with `self._cancel_event = threading.Event()`. Update `request_cancel()` to `self._cancel_event.set()`. Update `_state.set_cancel_check` callsite to `lambda: self._cancel_event.is_set()`. Update existing `test_worker_request_cancel_sets_flag` accordingly.
**Blocked by:** Nothing. Refactor next time touching `src/gui/worker.py`.
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
**Priority:** P2
**Effort:** M human / M with CC
**Why:** Users can't currently see what fixes were applied in the current session. The session manifest (2A) accumulates all applied fixes with timestamps, providing the ready data source. A UI panel showing this closes the UX half of the original pipeline-rescan idempotency report.
**Fix:** Create a new Dashboard-style card or sidebar panel that displays the session manifest: list of applied fixes with timestamps and revert status. Wire it to the `PipelineContext.fixes_applied` and manifest data. Persist the list until the next session starts.
**Blocked by:** Nothing — unblocked by v0.2.0.0 (pipeline-rescan + atomic manifest landed).
**Added:** 2026-05-23 (deferred from pipeline-rescan-idempotency-plan.md)

---

### T-017 — Test coverage for new pipeline phases + controller + workers
**Priority:** P2 — **COMPLETED 2026-05-28**

---

### T-018 — SystemStatsWorker missing deleteLater wire
**Priority:** P3
**Effort:** XS human / XS with CC
**Why:** Adversarial review on v0.2.0.0 flagged that `SystemStatsWorker` is the only QObject worker without `thread.finished.connect(worker.deleteLater)` wiring (the monitor-fix and monitor-refresh workers both have it). In `Dashboard.stop_polling`, dropping the last Python reference triggers `QObject.__del__` on the GUI thread while the worker thread may still be in `_tick()` — violates Qt's "destroy on owning thread" rule. Safe in practice on CPython, fragile under PyInstaller bundling.
**Fix:** In `Dashboard.start_polling`, add `self._worker_thread.finished.connect(self._worker.deleteLater)` before `self._worker_thread.start()`. Remove the manual `self._worker = None` in `stop_polling` (let deleteLater run); keep `_worker_thread = None` as the sentinel.
**Blocked by:** Nothing. Refactor next time touching `src/gui/widgets/dashboard.py`.
**Added:** 2026-05-28 (from /ship v0.2.0.0 adversarial review)

---

### T-019 — Cinebench output_file path `%` defense + 50 MB output cap
**Priority:** P4
**Effort:** S human / XS with CC
**Why:** Adversarial review on v0.2.0.0 flagged two related Cinebench output-path concerns. (1) The batch wrapper uses `start /b /wait "parentconsole" cmd.exe /C ""{cinebench_path}" {flag} > "{output_file}""`; if `output_file` resolves to a path containing `%` (e.g. running the exe from a `%`-containing CWD), `cmd.exe` would env-expand the redirect. `get_temp_dir()` returns a CWD-relative path, so a `%` in the user's username or working directory could leak. (2) Successful-path reads `output_file.read_text()` with no size cap — Cinebench R24 in verbose mode or a crashing run could produce a multi-MB file. The error path already caps at `raw[:500]`, but `cb_lines` is written to `cinebench_results.txt` without a line cap.
**Fix:** Add `if '%' in str(output_file)` to the `_run_cinebench` guard alongside the existing `"` check (or `^%`-escape the output path in the batch template). Add `if output_file.stat().st_size > 50_000_000` early-return as a tool-failure error. Cap `cb_lines` to the last 500 lines before writing `results_file`.
**Blocked by:** Nothing. No live exploit; defense in depth.
**Added:** 2026-05-28 (from /ship v0.2.0.0 adversarial review)

---

### T-020 — Strip triple-comment tail artifacts from Serena replace edits
**Priority:** P4 (cosmetic) — **COMPLETED 2026-05-28**

---

### T-021 — Maintainability polish (PEP-8 + `__all__` + docstring direction inversions)
**Priority:** P4 (cosmetic)
**Effort:** XS human / XS with CC
**Why:** /ship maintainability specialist on v0.2.0.0 flagged six low-priority polish items: missing trailing newline at `src/benchmarks/cinebench.py:289`; PEP-8 blank-line gaps in `src/gui/widgets/monitor_refresh_card.py` (between import and class definition, and between method definitions); `src/benchmarks/cinebench_monitor.py:9` docstring reversed direction ("re-exported from cinebench" should be "imported into cinebench so test patches work"); `__all__` declared in three sub-modules (`lhm_http.py`, `lhm_discovery.py`, `lhm_process_utils.py`) but no consumer uses star-import, so `__all__` is decorative; repeated `from src.utils.debug_logger import get_debug_logger` inside `Dashboard` method bodies that could be cached as `self._log` once in `__init__`.
**Fix:** Address opportunistically the next time each file is touched. None of these affects runtime; they only affect reader clarity.
**Blocked by:** Nothing.
**Added:** 2026-05-28 (from /ship v0.2.0.0 maintainability review)

---

## Completed

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
