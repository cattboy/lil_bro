# Pipeline Re-Scan Idempotency — Implementation Plan

**Status:** APPROVED — `/plan-ceo-review`, HOLD SCOPE, 2026-05-22
**Branch:** `feat/frontend-ui`
**Review mode:** HOLD SCOPE (bug fix, locked down — no scope expansion)

---

## Problem

In GUI mode, the optimization pipeline reads a **stale system snapshot**, so a
second "Run Optimization" re-detects and re-applies fixes that are already
applied.

Trace:

1. At GUI startup the splash pre-collects `full_specs.json` via
   `dump_system_specs()`. `StartupCoordinator.on_finished` loads it into
   `runtime["preloaded_specs"]`.
2. `PipelineController.start_pipeline()` builds
   `PipelineWorker(preloaded_specs=runtime["preloaded_specs"])` →
   `run_optimization_pipeline(preloaded_specs=…)` →
   `PipelineContext(specs=preloaded_specs)`.
3. `ScanPhase.run()` short-circuits: `if ctx.specs:` is truthy, so it **skips
   its own `dump_system_specs()`** and keeps the startup snapshot.
4. `ConfigPhase` runs 7 pure analyzers (`analyze_power_plan` etc.) against that
   stale snapshot → re-flags already-fixed settings as `WARNING` → re-proposes →
   `run_approval_flow` re-applies.

CLI mode is unaffected: `menu.py` calls `run_optimization_pipeline` with no
`preloaded_specs`, so `ScanPhase` re-dumps every run.

## Decision: Approach A — always re-scan

The live system is the source of truth; the startup snapshot is a dashboard
cache. The pipeline must scan fresh every run.

A "ledger of applied fixes" was **rejected**: a ledger drifts from reality
(external setting changes, GPU driver resets, Windows updates) and would make
lil_bro silently skip fixes the system genuinely needs. The analyzers are pure
and already return `OK` for correct state, so a fresh scan makes detection
idempotent for free — already-applied fixes produce no proposal.

## Resolved decisions

| ID | Decision |
|----|----------|
| **1A** | Fresh-first, snapshot-fallback. `ScanPhase` always dumps fresh; on `dump_system_specs()` returning `""` **or** a JSON-parse failure of the fresh file, it falls back to the startup snapshot and logs a warning. `preloaded_specs` survives as the explicit degraded-mode fallback. |
| **2A** | Revert manifest accumulates per app session. It spans first-fix-of-any-kind until an explicit revert, matching the single-System-Restore-point-per-session model. Manifest creation is lazy/idempotent so the pipeline **and** the dashboard monitor-fix share one manifest. Revert processes entries newest-first. |
| **4A** | Short-circuit `FinalBenchPhase` when zero auto-fixes were applied — no point measuring "after" when nothing changed. |

## File-by-file changes

> Refinement found during review: with 1A (snapshot-fallback), the snapshot must
> still reach `ScanPhase`, so `pipeline_controller.py` keeps passing
> `preloaded_specs` — its role changes from *primary input* to *fallback*. The
> behavioral fix localizes entirely to `ScanPhase`. `pipeline_controller.py` is
> **not** changed.

- **`src/pipeline/phase_scan.py`** — `ScanPhase.run()`: capture the preloaded
  `ctx.specs` as a local `snapshot`; always call `dump_system_specs()`; on
  success load the fresh file into `ctx.specs`; on `""` or JSON-parse failure set
  `ctx.specs = snapshot` and log a warning. Log the outcome
  (`dumped fresh` / `fell back to startup snapshot` / `no specs available`).
- **`src/utils/revert.py`** — Manifest lifecycle (2A): `start_session_manifest`
  stages a fresh manifest only if none is active; remove the
  archive-on-first-fix block from `append_fix_to_manifest`; make creation lazy so
  any fix path (pipeline or dashboard) creates/uses one shared manifest. Add a
  `threading.Lock` around the read-modify-write and `_pending_manifest` access
  (TODO 2, build-now).
- **`src/pipeline/base.py`** — `PipelineContext`: add `fixes_applied: int = 0`
  (default so `FinalBenchPhase` never hits `AttributeError`).
- **`src/pipeline/approval.py`** — `run_approval_flow` returns the count of
  **successful** `execute_fix()` calls (`execute_fix` already returns `bool`).
- **`src/pipeline/phase_config.py`** — capture that count into
  `ctx.fixes_applied`.
- **`src/pipeline/phase_final.py`** — `FinalBenchPhase.run()`: if
  `ctx.fixes_applied == 0`, return `PhaseResult("skipped", "No config changes
  applied — skipping final benchmark")`.
- **`src/gui/widgets/benchmark_row.py`** — a "final benchmark skipped — no
  changes applied" state so the missing "after" score is explained, not blank.

`phase_revert.py` already sorts manifest entries by `applied_at` and iterates
`reversed()`, so newest-first revert needs no change once the manifest holds all
entries.

## Test plan

```
NEW / CHANGED CODEPATH                       TEST
ScanPhase always dumps fresh                 unit: dumps even when ctx had preloaded specs
ScanPhase dump returns "" (1A)               unit: falls back to snapshot + logs warning
ScanPhase dump path but JSON corrupt (1A)    unit: falls back to snapshot
ScanPhase dump fails + no snapshot (1A)      unit: ctx.specs={}, ConfigPhase skips cleanly
TWO pipeline runs, 2nd run                   regression: 2nd run yields 0 proposals  ◀── key test
revert manifest accumulates across runs (2A) unit: 2 applying runs → 1 manifest, both entries
revert after 2 applying runs (2A)            unit: restores BOTH runs, newest-first
existing revert archival tests (2A)          invert test_archives_previous_session_on_first_fix
                                             + test_second_call_replaces_pending_manifest
FinalBench skip on zero fixes (4A)           unit: 0 fixes → FinalBench skipped; >0 → runs
```

## Outside-voice refinements folded in

An independent review (Claude subagent) surfaced three refinements, all folded
into the changes above:

- `PipelineContext.fixes_applied` needs a default of `0` (no `AttributeError`).
- 4A counts **successful** `execute_fix()` returns, not selected proposals
  (`execute_fix` already returns `bool`).
- The dashboard monitor-fix path (`_MonitorFixWorker`) never starts a manifest;
  lazy/idempotent manifest creation in 2A fixes this so dashboard fixes are
  revertible even as the first action of a session.

It also raised a false alarm (NVIDIA backup files going stale across runs) —
refuted: `backup_nvidia_profile` copies the export to the persistent
`get_backups_dir()` with run-unique filenames.

## Deferred to TODOS.md

- **TODO 1 — Persistent "what was applied / last run" UI panel** (P2). The
  post-2A session manifest is the ready data source. Closes the UX half of the
  original report.

## Out of scope

- Per-fix converge-to-desired-state (Approach C) — fresh scan already makes
  detection idempotent; re-applying a correct setting is a harmless no-op.
- Removing `preloaded_specs` entirely — it is the 1A degraded-mode fallback.
- Skipping `BaselineBenchPhase` on no-op runs — config is Phase 4; you cannot
  know it is a no-op until after the baseline benchmark already ran.

## Verification

- `git revert` is the rollback (pure code change, reversibility 5/5).
- No new modules under `src/gui/widgets/` → no `lil_bro.spec` change.
- Rebuild the exe after merge: `python -m PyInstaller lil_bro.spec --noconfirm`.

## Eng Review Refinements

Added by `/plan-eng-review` on 2026-05-22.

**Finding 1 — manifest `restore_point_created` honesty.** Under 2A's lazy
manifest creation, a dashboard monitor-fix done before any pipeline run would
create the manifest while no System Restore Point exists. `start_session_manifest`
defaults `restore_point_created=True`, which would be a lie. Resolution:

- Lazy creation reads `restore_point_created` from `ctx` when called inside the
  pipeline; defaults to `False` for the dashboard-fix path (no `ctx`, no restore
  point).
- `BootstrapPhase`, after creating the restore point, upgrades the flag to
  `True` on an already-existing manifest.
- Adds `src/pipeline/phase_bootstrap.py` to the touched files — **8 production
  files total**, at the complexity threshold but not over; the spread is
  inherent to 4A's cross-phase count signal, not accidental complexity.

**Implementation notes (folded in, no separate decision):**

- The 4A `FinalBenchPhase` skip guard must return a **distinct** message
  ("No config changes applied — skipping final benchmark"), separate from the
  existing "baseline did not run/complete" skips, so the benchmark-row skipped
  state (T5) shows the correct reason rather than looking like a failure.
- Sequence T2/T3: land the `revert.py` manifest-lifecycle refactor (lazy
  creation, drop archive, `threading.Lock`) as a structural commit with the
  inverted tests green, *then* the behavioral wiring. Never structural +
  behavioral in one commit.
- Lift the two ASCII diagrams in this doc into code comments: the manifest
  lifecycle into `revert.py`, the fresh-first/fallback flow into `ScanPhase`.

**Eng review verdict:** architecture sound, 1 issue (Finding 1, resolved),
0 critical gaps, test coverage plan complete (14 changed paths → 14 planned
tests). CLEARED.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 1 | clean | HOLD SCOPE; 1 critical gap (2A) found & resolved |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | clean | 1 issue, 0 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | not run — trivial UI (one widget state) |

- **UNRESOLVED:** 0
- **VERDICT:** CEO + ENG CLEARED — ready to implement.
