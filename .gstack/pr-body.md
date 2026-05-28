## Summary

Ships v0.2.0.0 — the PySide6 desktop GUI, pipeline rescan idempotency, six refactor extractions, and the full review-fix bundle from /review. 72 commits since PR #22 merged.

**PySide6 desktop GUI** (~5,000 LOC under `src/gui/`)
- Replaces CLI-only experience with windowed app: dashboard (live thermals / mouse polling / monitor refresh tiles), optimization pipeline view with phase-card progress, batch fix selection, approval/confirm dialogs, AI Setup, animated splash. CLI preserved via `lil_bro.exe --terminal`.
- Stop button + global hotkeys (Esc/Q/Enter) using `Qt.DirectConnection` to bypass the worker-thread event loop deadlock.
- GUI-mode output sinks for `formatting.py` and `progress_bar.py` so all `print_*` and progress calls route through Qt signals into the output panel.

**Pipeline rescan idempotency** (`docs/pipeline-rescan-idempotency-plan.md`)
- `ScanPhase` always re-dumps live specs; falls back to the startup snapshot only on dump failure. Running the pipeline twice in one session now yields 0 proposals on the second run.
- Session manifest accumulates across runs instead of being reset; one Revert undoes everything from every run in newest-first order.
- `FinalBenchPhase` skips with a distinct "no changes applied" message when `fixes_applied == 0`.

**Dashboard race-condition fixes** (CR-1..CR-5 from /review)
- `on_monitor_fix_requested` rejects clicks during a pipeline run and double-clicks while a fix is in flight.
- `_run_app_cleanup` waits for both `monitor_fix_thread` and `monitor_refresh_thread` before LHM teardown.
- `_write_manifest` atomic via `.tmp` + `os.replace`. A process kill mid-write no longer wipes session revert data.
- `_MonitorFixWorker` docstring corrected + future-deadlock-trap warning added.
- `refresh_monitor_card` got the same pipeline-running + shutdown-wait guards as the fix path (caught by adversarial review on this PR's own diff).

**Six refactor extractions** (atomic, behavior-preserving)
- `theme.py` -> `theme/` package (tokens, helpers, stylesheet + 4 domain modules)
- `cinebench.py` -> discovery + monitor + parser
- `lhm_sidecar.py` -> discovery + http + process_utils
- `formatting.py` -> `_console.py`
- `app.run()` -> `PipelineController` + `StartupCoordinator`

**Security hardening**
- LHM HTTP `resp.read(10 * 1024 * 1024)` cap across 3 sites (lhm_http, thermal_monitor, lhm_sidecar)
- Cinebench path rejected if it contains `"` before batch-file interpolation
- `_find_elevated_pid` validates `exe_name` against `^[\w.\-]+\.exe$` before tasklist filter

**Performance polish** (5s polling loop)
- `_tick_count` / `_apply_count` initialized in `__init__` instead of `getattr` fallback
- `SystemStatsWorker._tick` and widget renders hoisted hot-path imports (`psutil`, `propose_for_check`, debug logger)
- `splash.on_init_step` drops `list()` wrapper around `_STEP_NAMES.index()`

**Architectural refactors**
- `_MonitorRefreshWorker` moves the 200-800ms `EnumDisplayDevicesW` + WMI probe off the GUI thread
- `StartupOrchestrator` preloads `full_specs.json` on its worker thread instead of the post-splash main-thread `json.load`
- Dashboard `QTimer.singleShot` converted from lambda closure to 3-arg bound method (Qt auto-cancels on context destroy)

## Test Coverage

| Category | Covered | Gaps | % |
|---|---|---|---|
| `revert.py` (atomic + thread + idempotency) | 12/12 | 0 | 100% |
| `StartupCoordinator` (monitor guards + refresh) | 8/11 | 3 | 73% |
| `PipelineController` | 1/10 | 9 | 10% |
| `worker.py` (4 new workers) | 1/9 | 8 | 11% |
| `ScanPhase` (fallback + mouse) | 4/7 | 3 | 57% |
| `FinalBenchPhase` (new guards) | 3/7 | 4 | 43% |
| `BenchmarkOptInPhase` / `ApplyPhase` | 0/6 | 6 | 0% |
| `BaselineBenchPhase` (new branches) | 0/5 | 5 | 0% |
| GUI widgets (monitor/splash/output/stat/statusbar) | 5/19 | 14 | 26% |
| `BenchmarkRow` widget | 11/11 | 0 | 100% |
| `MousePollCard` widget | 4/8 | 4 | 50% |
| `bridge.py` (new sinks) | 2/6 | 4 | 33% |
| `cinebench` (GUI cancel + STARTUPINFO + sub-modules) | 11/11 | 0 | 100% |
| `lhm` sub-modules | 5/5 | 0 | 100% |
| `thermal_gate` refactor | 6/6 | 0 | 100% |
| `MainWindow` (new nav/stop/shortcuts) | 12/12 | 0 | 100% |
| **TOTAL** | **86/153** | **67** | **~56%** |

Tests: 651 -> 671 (+20 new). All passing.

Top gaps tracked as T-017 in TODOS.md: `PipelineController`, `BenchmarkOptInPhase`, `ApplyPhase`, `BaselineBenchPhase` new branches, `SystemStatsWorker._tick`, worker `run` methods, `MonitorRefreshCard.set_display`, `SplashDialog`, `GuiBridge.abort_pending`. High-risk concurrency and manifest paths ARE 100% covered.

## Pre-Landing Review

`/review` on commit `14353e2` (the last review-fix commit before this PR's ship-cycle) — **CLEAN**. Quality 9.5. Specialists: testing 21 informational, maintainability 7 informational, security 5 informational, performance 11 informational, red-team 12 (2 critical -> both fixed in this PR). All 27 fixes committed atomically.

Adversarial pass during /ship caught one additional follow-up: `refresh_monitor_card` was missing the same guards as `on_monitor_fix_requested` (CR-1/CR-3 shape). Fixed in commit `4275297`.

## Design Review

Frontend code is touched extensively but `/design-review` was not run on the running app. Recommended post-merge: `/design-review` against `dist/lil_bro.exe` for a real visual QA pass on the desktop UI.

## Eval Results

No prompt-related files changed — evals skipped.

## Scope Drift

**Scope Check: CLEAN.** Every changed top-level directory maps to stated intent (pipeline-rescan idempotency, refactor extractions, review fixes, design system docs).

## Plan Completion

Plan: `C:\Users\Owner\.claude\plans\happy-hatching-ladybug.md` (the /review fix plan)

**24/24 diff-verifiable items DONE.** 5 deferred groups (T/M/Adv-8/9/10/11/12) by plan design.

### CR Group — Critical Fixes (5/5)
- [x] CR-1 pipeline-running guard in `on_monitor_fix_requested` + regression test
- [x] CR-2 double-click guard in same method + regression test
- [x] CR-3 `monitor_fix_thread.wait(3000)` in `_run_app_cleanup`
- [x] CR-4 atomic manifest write + 3 regression tests
- [x] CR-5 `_MonitorFixWorker` docstring + deadlock warning

### Group A — Docs + Dead Code (4/4)
### Group BC — Security Hardening (5/5)
### Group D — Performance Polish (5/5)
### Group E — Architectural Refactors (3/3)
### Adversarial follow-up (post-plan): refresh_monitor_card same-shape guards

### Manual verification required (EXTERNAL-STATE, post-merge)
- [ ] V1: pipeline running + click Fix Now -> "suppressed" log
- [ ] V2: double-click Fix Now -> "already in progress" log
- [ ] V3: click Fix Now + close window -> manifest complete JSON
- [ ] V4: kill exe mid-fix -> manifest complete or absent (never truncated)
- [ ] V5: end-to-end idempotency (2nd pipeline run -> 0 proposals)
- [ ] V6: bundled-exe smoke (`dist/lil_bro.exe` launches + Dashboard widgets render)

## Verification Results

Skipped — desktop app, no dev server for browse-based verification. Manual smoke required (V1-V6 above).

## TODOS

No existing items completed by this PR. Five new follow-ups added:
- **T-017** Test coverage for new pipeline phases + controller + workers (P2)
- **T-018** SystemStatsWorker missing `deleteLater` wire (P3)
- **T-019** Cinebench output_file `%` defense + 50 MB output cap (P4)
- **T-020** Strip triple-comment tail artifacts from Serena replace edits (P4, cosmetic)
- **T-021** Maintainability polish (PEP-8 + `__all__` + docstring direction inversions) (P4, cosmetic)

T-016 (persistent "what was applied" UI panel) is **unblocked** by this PR — session manifest infrastructure now in place.

## Documentation

- **README.md**: Status section updated to v0.2.0.0 GUI release; Architecture section notes PySide6 as default UI; test count corrected to 671.
- **CONTRIBUTING.md**: Project structure tree expanded with full `src/gui/` package (app, pipeline_controller, startup_coordinator, worker, theme/, widgets/, windows/), extracted sub-modules under `benchmarks/` (cinebench_discovery, cinebench_parser, cinebench_monitor) and `collectors/sub/` (lhm_http, lhm_discovery, lhm_process_utils); test count corrected from 882 to 671; "Terminal UI only" rule updated to reflect PySide6 shipped.
- **docs/ARCHITECTURE.md**: File tree updated with full `gui/` tree and all refactored sub-modules; pipeline section notes rescan idempotency and FinalPhase skip-when-no-fixes behavior; new **GUI Architecture** section added describing the startup sequence and dashboard fix-button threading model.
- **CLAUDE.md**: "Terminal UI only" rule updated to PySide6 + --terminal; test count updated to 671; key entry points split into GUI path and CLI path.

### Documentation Debt
- `src/gui/widgets/` — reference coverage in ARCHITECTURE.md only; no how-to for adding new dashboard cards beyond the CLAUDE.md pattern note. Run `/document-generate` to produce a widget-authoring how-to.
- `src/gui/theme/` — new 7-module QSS token package has no explanation doc for the Python layer (DESIGN.md covers visual tokens but not the stylesheet assembly pipeline).
- `src/agent_tools/quick_status.py` — new module, reference only in ARCHITECTURE.md; no how-to for adding new fast-path dashboard reads.

## Test plan

- [x] All pytest tests pass (671 tests, 0 failures)
- [x] Pre-landing review CLEAR (quality 9.5)
- [x] Adversarial review fixes committed (CR-1..CR-5 + refresh_monitor_card guard follow-up)
- [x] Plan completion: 24/24 DONE
- [ ] Manual: V1-V6 smoke on real hardware (post-merge)
- [ ] Manual: `python -m PyInstaller lil_bro.spec --noconfirm` + launch `dist/lil_bro.exe` to verify Dashboard widgets render in the bundled exe

🤖 Generated with [Claude Code](https://claude.com/claude-code)
