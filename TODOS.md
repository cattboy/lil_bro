# TODOS

Items flagged during reviews but deferred from current PRs.
Format: Priority | Effort (human / CC) | Context

---

## Open

### T-001 — Future-proof formatting.py API for rich/GUI backend
**Priority:** P2
**Effort:** L human / M with CC
**Why:** All `print_*` functions in `formatting.py` call `print()` directly and are tightly coupled to colorama. When the PyQt GUI arrives (planned, deferred), a GUI layer would need to intercept terminal output and display it in a widget instead. A `return_str=False` default param on each function enables this without changing any call sites.
**How to apply:** Add `return_str: bool = False` param to all print_* functions. When `True`, return the formatted string instead of printing. The GUI backend calls them with `return_str=True`; the terminal path stays unchanged.
**Blocked by:** PyQt GUI architecture decision (Phase 5).
**Added:** 2026-03-24 (from /plan-ceo-review, Week 6 terminal UI redesign)

---

### T-006 — Observability & Instrumentation
**Priority:** P3
**Effort:** L human / L with CC
**Why:** No phase timing snapshots, no per-check success/failure ratios, no metrics aggregation. Logs exist but no structured performance data. Value only materializes when the codebase grows significantly or multiple contributors are involved.
**Fix:** Optional metric collection via `@instrument` decorator or a metrics registry.
**Blocked by:** Nothing. Defer until codebase or team grows.
**Added:** 2026-04-11 (merged from todo.md Issue 3.3)

---

### T-009 — Decide: wire phase-row progress cards in GUI output view, or remove them
**Priority:** P2 — **RESOLVED 2026-05-19**
**Decision:** Remove PhaseRow, replace with live benchmark score cards.
**What shipped:** `BenchmarkRow` (5 cards: BASELINE | POST-OPT | DELTA | CPU PEAK | STATUS) replaces `PhaseRow` in the output view. Cards update live via `benchmark_score_ready` signal emitted by `notify_benchmark_score()` after each Cinebench run. `phase_row.py`, `phase_card.py`, `test_phase_card.py` deleted. `test_benchmark_row.py` added (12 tests). STATUS flow: Pending → Running (pipeline starts) → Benchmarking (Cinebench subprocess active, via `benchmark_started` signal from `notify_benchmark_started()` in `cinebench.py`) → Running (score arrives) → Complete (pipeline finishes).
**Cleanup debt:** `phase_changed = Signal(int, str)` remains in `PipelineSignals` and `_on_phase_changed` alias in `app.py` as deprecation gravestones (keep stale standalone connection line harmless). Remove both when `run()` is next rewritten.

---

### T-010 — Verify `status_bar_widget` + `benchmark_row` hiddenimports in lil_bro.spec
**Priority:** P3 (verification task)
**Effort:** XS human / XS with CC
**Why:** Per `CLAUDE.md`, modules under `src/gui/widgets/` lazily imported inside method bodies must be in `hiddenimports`. `benchmark_row` was added (replaced `phase_card`). `status_bar_widget` remains absent. T-009 is now resolved — `phase_row` question is moot.
**Fix:** Run `python build.py` and smoke-test `dist/lil_bro.exe`. If BenchmarkRow or StatusBarWidget fails to render in the bundled exe, add the missing entry to `lil_bro.spec` hiddenimports:
- `'src.gui.widgets.status_bar_widget',` after `splash`

**Blocked by:** Nothing.
**Added:** 2026-05-18 (updated 2026-05-19 after T-009 resolved)

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

## Completed

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
