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
**Priority:** P2
**Effort:** S human / S with CC (wire) or XS / XS (remove)
**Why:** `PhaseRow` along the top of the output view renders 5 cards (Bootstrap / System Scan / AI Analysis / Apply Fixes / Verify) but they never leave PENDING during a pipeline run. Two reasons:
1. Nothing in the pipeline ever emits `PipelineSignals.phase_changed`. Grep for `phase_changed.emit` returns zero matches. The signal is connected (`bridge.signals.phase_changed.connect(_on_phase_changed)` in `src/gui/app.py:287`) but the producer side was never written.
2. The signal signature is `Signal(int, str)` (`src/gui/signals.py:22`), but the slot expects `(phase_name: str, status: str)` (`src/gui/app.py:276`). If anything ever did emit it today, the int would land in `phase_name` and `update_phase()` would silently no-op (dict lookup miss).

The terminal log panel already shows phase progress in real time as the pipeline prints, so the card row may be redundant decoration. Decision needed before /ship: keep + wire, or delete.

**Fix — if wiring:**
- Change `phase_changed = Signal(str, str)` to match the slot (`src/gui/signals.py:22`).
- Add a phase-transition callback to `run_optimization_pipeline()` (`src/pipeline/phases.py`) so `PipelineWorker` can emit `(phase_name, status)` across the bridge. Mirror the `_state.set_cancel_check` injection pattern.
- Map pipeline `Phase.name` → GUI-facing names listed in `src/gui/widgets/phase_row.py:_PHASE_NAMES`.
- Hide the `_progress` bar on each card (currently only shown when ACTIVE — already correct, just verify).

**Fix — if removing:**
- Delete `PhaseRow` widget construction in `src/gui/windows/main_window.py:207-208` and the import at line 173.
- Drop `phase_changed` from `PipelineSignals`, the `_on_phase_changed` slot in `app.py`, and `update_phase` on `MainWindow`.
- Remove `src/gui/widgets/phase_row.py` + `tests/test_phase_card.py` + `tests/test_phase_row.py` (if exists).
- Also closes T-009-adj: the Fix 2 hiddenimports question for `phase_row` becomes moot.

**Blocked by:** Nothing. Decide as part of /ship review.
**Added:** 2026-05-18 (deferred from /review fix-set; cards visible in V2 GUI but inert — terminal log already covers progress)

---

### T-010 — Verify or skip `phase_row` + `status_bar_widget` hiddenimports in lil_bro.spec
**Priority:** P3 (verification task)
**Effort:** XS human / XS with CC
**Why:** Per `CLAUDE.md`, new modules under `src/gui/widgets/` must be added to `hiddenimports` in `lil_bro.spec` because PyInstaller's static analyzer can miss lazy imports inside method bodies. Both `src/gui/widgets/phase_row.py` and `src/gui/widgets/status_bar_widget.py` are lazy-imported in `src/gui/windows/main_window.py:81,173` and were absent from the spec. Empirical observation: the cards and custom status bar **do** render in the current bundled exe, so PyInstaller may be picking them up via a different reachability path. Decision deferred pending: (a) a fresh `python build.py` + smoke confirming the widgets still render, and (b) the T-009 keep-or-remove decision (if PhaseRow is removed, only `status_bar_widget` remains to verify).
**Fix:** After T-009 lands, run `python build.py` and smoke-test the bundled `dist/lil_bro.exe`. If either widget fails to render, add the missing line(s) to the alphabetized `hiddenimports` list in `lil_bro.spec`:
- `'src.gui.widgets.phase_row',` after `phase_card`
- `'src.gui.widgets.status_bar_widget',` after `splash`

**Blocked by:** T-009 decision.
**Added:** 2026-05-18 (deferred from /review Fix 2; user reverted the proactive addition pending empirical verification)

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
