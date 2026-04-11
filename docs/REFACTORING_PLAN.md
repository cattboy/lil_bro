# lil_bro Refactoring Plan — Remaining Work

**Branch**: `refactor/priority-1-improvements`
**Plan started**: 2026-04-07 | **Trimmed**: 2026-04-11
**Full history**: `docs/DONE.md`

---

## Status

All Priority 1, Priority 2-A, Priority 2-B, Priority 3-A, and config auto-generation issues are **done**. See `docs/DONE.md` for details. Test count: 407 passing.

---

## Remaining Issues

### Issue 1.5 + T-005 — Phase Execution Status Not Visible to Orchestrator

**Priority**: 3 (Nice to Have) | **Effort**: S

**Location**: `src/pipeline/phases.py`, all `src/pipeline/phase_*.py`

**Problem**: All `Phase.run()` methods return `None`. Status (ran/skipped/failed) is communicated only via side effects on `PipelineContext`. The orchestrator has no visibility into whether a phase ran, was skipped, or errored.

**Fix**: Add `PhaseResult` dataclass to `src/pipeline/base.py`. Update all 5 phase `run()` methods to return `PhaseResult`. Update orchestrator in `phases.py` to capture and log results.

```python
# src/pipeline/base.py — add:
@dataclass
class PhaseResult:
    status: Literal["completed", "skipped", "failed"]
    message: str = ""
    error: Optional[str] = None
```

**Files**:
- `src/pipeline/base.py` — add `PhaseResult`
- `src/pipeline/phases.py` — capture return values in orchestrator loop
- `src/pipeline/phase_bootstrap.py` — return `PhaseResult`
- `src/pipeline/phase_scan.py` — return `PhaseResult`
- `src/pipeline/phase_baseline.py` — return `PhaseResult`
- `src/pipeline/phase_config.py` — return `PhaseResult`
- `src/pipeline/phase_final.py` — return `PhaseResult`
- `tests/test_phase_final.py` — update mocks for return value
- `tests/test_phase_config.py` — update for return value

---

### Issue 3.4 — Lifecycle Management Split

**Priority**: 3 (Nice to Have) | **Effort**: M

**Location**: `src/main.py`, `src/pipeline/phases.py`, `src/pipeline/phase_baseline.py`, `src/pipeline/phase_final.py`

**Problem**: `LHMSidecar` is created in `main.py` and passed through to the pipeline. `ThermalMonitor` is instantiated in `phases.py` and its `start()`/`stop()` lifecycle is split between `phase_baseline.py` and `phase_final.py`. No unified ownership or cleanup guarantee.

**Fix**: Could use context manager pattern for both resources to guarantee cleanup even on exception. Low urgency — current pattern works and is tested.

---

### Issue T-001 — Future-proof formatting.py for GUI

**Priority**: 3 (Nice to Have) | **Effort**: M

**Location**: `src/utils/formatting.py`

**Problem**: All `print_*` functions call `print()` directly. There is no pluggable output backend. If a GUI is ever added, every `print_*` call would need to be updated individually.

**Fix**: Abstract the output sink (e.g., via an injectable callback or strategy object) so that console and GUI output share the same formatting logic. **Hold until GUI is actually requested** — premature abstraction otherwise.

---

### Issue 3.3 — Observability & Instrumentation Missing

**Priority**: 3 (Nice to Have) | **Effort**: L

**Location**: N/A (not implemented)

**Problem**: No phase timing snapshots, no per-check success/failure ratios, no metrics aggregation. Logs exist but no structured performance data.

**Fix**: Optional metric collection via `@instrument` decorator or a metrics registry. Lowest priority for a solo CLI tool — added value only when the codebase grows.

---

## Explicitly Out of Scope

Decided during eng-review and Priority 2-B analysis. Do not reopen without a strong new reason.

| Issue | Decision |
|-------|----------|
| **Setter interface Protocol** (2.5) | `display_setter.py`'s `(bool, str)` tuple return is intentional — the dry_run/apply two-phase pattern requires it. Not changing. |
| **Phase Dependency Framework** (PhaseContract classes) | Over-engineered for a 4,000-line solo tool. The null guard in `phase_final.py` is sufficient. |
| **CollectorResult generic type** | Deferred — codebase not grown enough to justify. |
| **FallbackStrategy Protocol** (3.1) | The four fallback paths have different triggers, return types, and caller patterns. A unified abstraction would add indirection without reducing complexity. Closed. |

---

*For completed work see `docs/DONE.md`.*
