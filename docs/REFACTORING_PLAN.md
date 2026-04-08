# lil_bro Architecture Analysis & Refactoring Plan

**Status**: Analysis Complete | Awaiting User Review
**Date**: 2026-04-07
**Scope**: Identify improvement areas in ARCHITECTURE.md and recommend refactoring strategy

---

## Executive Summary

lil_bro's architecture is **well-structured for its current scope** (5-phase optimization pipeline for gaming PCs) but exhibits several refactoring opportunities across three layers:

1. **Pipeline Orchestration** (phases.py, base.py) — Hidden phase dependencies, implicit state contracts
2. **Agent Tools & Collectors** (agent_tools/, collectors/) — Code duplication, inconsistent error handling, weak abstractions
3. **Supporting Infrastructure** (utils/, llm/, benchmarks/) — Scattered fallback logic, missing configuration layer, weak observability

**Total codebase**: ~4,000 lines across 40+ files. Most issues are **maintainability** concerns rather than functional bugs.

---

## Context

This codebase:
- ✅ Has strong logical separation (collect → analyze → fix)
- ✅ Implements human-in-the-loop approval pattern consistently
- ✅ Falls back gracefully when tools fail (LLM absent, Cinebench missing, etc.)
- ❌ Has implicit phase ordering contracts (Phase 5 crashes if Phase 3 skipped)
- ❌ Duplicates code in critical paths (NVIDIA profile, display enumeration)
- ❌ Mixes error handling strategies (raises vs returns vs tuples)
- ❌ Lacks configuration schema for thresholds/timeouts

**Goal**: Maintain current functionality while improving testability, maintainability, and resilience.

---

## Layer 1: Pipeline Orchestration Issues

### Current State
- 5 phases defined in `phases.py` with hardcoded ordering in `_PHASES` list
- Context state managed via `PipelineContext` dataclass with loose typing
- Phase dependencies implicit: Phase 5 requires Phase 3's `ctx.runner` to exist
- Error handling inconsistent: some phases use try/except, others don't

### Key Issues Identified

#### **Issue 1.1: Phase Dependency Contracts Are Implicit** ⚠️ CRITICAL
**Location**: `src/pipeline/phases.py`, `phase_baseline.py`, `phase_final.py`

**Problem**:
- Phase 5 (FinalBench) depends on Phase 3 (BaselineBench) creating `ctx.runner`
- If Phase 3 skips due to thermal protection, Phase 5 crashes: `AttributeError: 'NoneType' has no attribute 'run_benchmark'`
- No validation that required context fields exist before phase execution

**Example**:
```python
# phase_final.py line 31 — assumes ctx.runner exists from phase 3
final = ctx.runner.run_benchmark(full_suite=True, lhm_available=ctx.lhm_available)
# If phase_baseline skipped thermal gate, ctx.runner is None → CRASH
```

**Impact**: Hard to reorder phases, skip phases, or make phases conditional. Surprises developers.

**Refactoring**: Add phase precondition validation and explicit dependency contracts.

---

#### **Issue 1.2: Context Field Defaults Scattered Across Phases** ⚠️ MODERATE
**Location**: `phase_baseline.py` lines 23-24, 30-31

**Problem**:
- `ctx.baseline_result` and `ctx.peak_temps` initialized multiple times
- No single source of truth for skip result structure
- Changing skip behavior requires updating multiple locations

**Example**:
```python
# Line 23-24: Initialize on thermal protection failure
ctx.baseline_result = dict(_SKIP_RESULT)
ctx.peak_temps = {}

# Line 30-31: Re-initialize with different value
ctx.baseline_result = {"status": "skipped", "message": "Skipped due to..."}
ctx.peak_temps = {}
```

**Impact**: Maintenance burden, inconsistent skip semantics.

**Refactoring**: Move context defaults to dataclass with typed defaults or factory functions.

---

#### **Issue 1.3: Global Mutable LLM State (_state.py)** ⚠️ MODERATE
**Location**: `src/pipeline/_state.py`

**Problem**:
- Module-level `_llm` variable stored globally to avoid circular imports
- Type is `object`, not properly typed
- LLM instance reused across multiple pipeline runs (no lifecycle reset)
- Untestable without global state mutation

**Impact**: Can't run tests without side effects, hard to compose pipelines, type checking weak.

**Refactoring**: Move LLM to PipelineContext, ensure proper initialization.

---

#### **Issue 1.4: Thermal Safety Logic Duplicated** ⚠️ MODERATE
**Location**: `thermal_gate.py` used in both `phase_baseline.py` and `phase_final.py`

**Problem**:
- Both phases call `require_thermal_protection()` with identical pattern
- Both phases re-implement skip result initialization
- Thermal monitoring lifecycle split: Phase 2 starts LHM, Phase 3 starts ThermalMonitor, Phase 5 reuses it

**Impact**: Hard to change thermal strategy uniformly, unclear lifecycle state.

**Refactoring**: Extract thermal management to reusable component with clear state markers.

---

#### **Issue 1.5: Phase Execution Status Not Visible to Orchestrator** ⚠️ MODERATE
**Location**: `phases.py` orchestrator loop

**Problem**:
- Phases have internal skip/abort logic but orchestrator has no visibility
- Each phase decides independently whether to skip
- No way to detect: "Did phase actually run or was it skipped?"

**Impact**: Can't build conditional chaining, progress reporting incomplete, hard to debug.

**Refactoring**: Return phase result with status (ran/skipped/failed) to orchestrator.

---

#### **Issue 1.6: Error Handling Inconsistent Across Phases** ⚠️ MODERATE
**Location**: All phase files

**Pattern**:
- Bootstrap: try/except with PipelineAborted
- Scan: try/except, logs and continues
- Baseline: No exception handling (assumes success)
- Config: No exception handling
- Final: No exception handling

**Impact**: Unexpected exceptions crash pipeline, no consistent recovery strategy.

**Refactoring**: Define phase error contract with consistent handling.

---

### Refactoring Strategy: Layer 1

**Create Phase Dependency Framework**:
```python
# New: src/pipeline/phase_contract.py
@dataclass
class PhaseContract:
    name: str
    requires: list[str]  # ["lhm_available", "specs"]
    provides: list[str]  # ["baseline_result", "runner"]
    must_run: bool = True

@dataclass
class PhaseResult:
    name: str
    status: Literal["completed", "skipped", "failed"]
    error: Optional[str] = None
    context_updates: dict = field(default_factory=dict)
```

**Benefits**:
- Explicit contracts prevent implicit assumptions
- Orchestrator can validate preconditions before running phases
- Easy to skip, reorder, or make conditional

---

## Layer 2: Agent Tools & Collectors Issues

### Current State
- 8 analyzers in `agent_tools/` follow consistent return dict format ✅
- Collectors in `collectors/` use graceful degradation pattern ✅
- But error handling strategy differs: some raise, some return dicts, some return tuples ❌
- Code duplication in critical paths (NVIDIA profile, display enumeration) ❌

### Key Issues Identified

#### **Issue 2.1: NVIDIA Profile Code Duplication** ⚠️ HIGH
**Location**: `src/agent_tools/nvidia_profile.py` (analyzer) and `src/agent_tools/nvidia_profile_setter.py` (setter)

**Problem**:
- Both files have identical `calculate_fps_cap()` function (~5 lines)
- Both files extract GPU generation independently
- Setter imports some functions from analyzer to avoid duplication, but not all

**Impact**: Maintenance burden, inconsistent when function changes.

**Refactoring**: Extract shared NVIDIA utilities to `src/utils/nvidia_utils.py`.

---

#### **Issue 2.2: Display Mode Enumeration Path Duplication** ⚠️ MODERATE
**Location**: `src/collectors/sub/monitor_dumper.py` and `src/agent_tools/display_setter.py`

**Problem**:
- Both have `DEVMODE` ctypes struct definition
- Both implement mode enumeration logic
- Setter re-enumerates modes instead of using collected specs

**Impact**: Two paths to enumerate modes, risk of divergence, not DRY.

**Refactoring**: Consolidate DEVMODE and enumeration to `src/utils/display_utils.py`.

---

#### **Issue 2.3: Error Handling Strategy Inconsistent** ⚠️ HIGH
**Location**: Across `agent_tools/` and `collectors/`

**Problem**:
- Collectors: Mix of raising (`FileNotFoundError`, `RuntimeError`) and returning error dicts
- Analyzers: Some raise `ScannerError`, some return structured dicts
- Setters: Heterogeneous signatures and return types

**Example**:
```python
# In power_plan.py
def set_active_plan(guid):
    try:
        subprocess.run(...)
    except Exception as e:
        raise ScannerError(f"Failed: {e}")  # ← Raises

# In game_mode.py
def set_game_mode(enabled):
    try:
        winreg.SetValue(...)
    except Exception as e:
        raise ScannerError(f"Failed: {e}")  # ← Raises

# In display_setter.py
def apply_display_mode(device, mode, ...):
    try:
        ctypes.windll.user32.ChangeDisplaySettingsEx(...)
    except Exception:
        return (False, "Failed")  # ← Returns tuple
```

**Impact**: Callers must handle mixed error types, inconsistent testing, hard to propagate errors uniformly.

**Refactoring**: Create unified error hierarchy and result type.

---

#### **Issue 2.4: Missing Abstraction Layers** ⚠️ MODERATE
**Location**: Multiple

**Problems**:
1. **No CollectorResult type** — Collectors return wildly different formats
   - `get_nvidia_smi()` → `list[dict]`
   - `get_wmi_specs()` → nested `dict`
   - `get_nvidia_profile()` → `{"available": True/False, ...}`

2. **No unified subprocess wrapper** — Raw calls scattered across 5+ files
   - Each reimplements timeout, error parsing, logging
   - No consistent output format

3. **No specs schema definition** — Each analyzer assumes specific keys without validation
   - Risk: Typo in collector → Silent failure in analyzer

**Impact**: Hard to understand data flow, risk of silent failures.

**Refactoring**: Define typed abstractions for common patterns.

---

#### **Issue 2.5: Setter Interface Contract Missing** ⚠️ MODERATE
**Location**: All setter files

**Problem**:
- Each setter has different signature:
  - `display_setter`: `(device, mode, persist, dry_run)` → `(bool, str)`
  - `nvidia_profile_setter`: `(specs, refresh_hz, gpu_generation)` → `bool`
  - `game_mode`: `(enabled)` → `bool`
  - `power_plan`: `(guid)` → `None`

**Impact**: Dispatch logic in `fix_dispatch.py` must handle each individually, hard to add new setters.

**Refactoring**: Define setter interface protocol.

---

### Refactoring Strategy: Layer 2

**Create error hierarchy**:
```python
# src/utils/errors.py (expand from 16 lines to 60+ lines)
class ToolError(Exception):
    """Base for all tool errors"""

class CollectorError(ToolError):
    """Data collection failed"""

class AnalysisError(ToolError):
    """Hardware analysis failed"""

class FixerError(ToolError):
    """Remediation failed"""
```

**Create result types**:
```python
# src/utils/result_types.py
@dataclass
class CollectorResult(Generic[T]):
    success: bool
    data: T | None = None
    error: str | None = None

@dataclass
class FixerResult:
    success: bool
    message: str
    changed: bool = False
```

**Create setter protocol**:
```python
class Setter(Protocol):
    def fix(self, specs: dict) -> FixerResult:
        """Apply remediation. Raises FixerError on failure."""
        ...
```

---

## Layer 3: Supporting Infrastructure Issues

### Current State
- Logging architecture is excellent (action_logger.py, debug_logger.py) ✅
- UI abstraction is strong (formatting.py, progress_bar.py) ✅
- But fallback logic is scattered across 5+ modules ❌
- Missing: configuration schema for thresholds/timeouts ❌
- Missing: observability/metrics collection ❌

### Key Issues Identified

#### **Issue 3.1: Fallback Logic Scattered & Implicit** ⚠️ MODERATE
**Location**: Various

**Problem**:
- LLM fallback: `action_proposer.py` has static templates dict
- Cinebench fallback: `cinebench.py` has CPU stress fallback
- Model fallback: `model_loader.py` returns None
- Thermal fallback: `thermal_monitor.py` returns empty dict
- No unified strategy, hard to reason about graceful degradation

**Impact**: Hard to understand what happens when component fails, hard to test fallback paths.

**Refactoring**: Create `src/strategy.py` with `FallbackStrategy` protocol.

---

#### **Issue 3.2: Configuration Hardcoded Throughout** ⚠️ MODERATE
**Location**: Multiple files

**Examples**:
```python
# cinebench.py
_CINEBENCH_TIMEOUT = 600

# thermal_monitor.py
_WATCHDOG_THRESHOLD = 95.0
_DEFAULT_POLL_INTERVAL = 1.0

# action_proposer.py
(hardcoded JSON prompt structure)
```

**Impact**: Hard to tune behavior without code changes, no per-user config options.

**Refactoring**: Create `src/config.py` with validated configuration schema.

---

#### **Issue 3.3: Observability & Instrumentation Missing** ⚠️ LOW
**Location**: N/A (not implemented)

**Problem**:
- No timing snapshots for phases
- No resource usage tracking
- No success/failure ratio per check
- Logs exist but no aggregation

**Impact**: Hard to debug performance, no trend analysis possible.

**Refactoring**: Optional metric collection via `@instrument` decorator.

---

#### **Issue 3.4: Phase Lifecycle Management Split Across Modules** ⚠️ MODERATE
**Location**: phases.py, phase_*.py, thermal_gate.py, lhm_sidecar.py

**Problem**:
- LHM sidecar lifecycle: Created in main.py, used throughout, stopped in finally block
- Thermal monitor lifecycle: Started in phase_baseline, stopped in phase_final, reused
- No unified lifecycle management pattern

**Impact**: Hard to trace ownership, cleanup errors possible.

**Refactoring**: Create resource manager pattern for long-lived objects.

---

#### **Issue 3.5: Circular Import Guards (Anti-Pattern)** ⚠️ LOW
**Location**: `integrity.py`, potential others

**Problem**:
```python
# integrity.py line ~30
if os.path.getenv("DEBUG"):
    from src.utils.formatting import print_warning  # Lazy import to avoid cycle
```

**Impact**: Type checkers can't validate, confuses readers.

**Refactoring**: Restructure imports to avoid cycles rather than guard them.

---

### Refactoring Strategy: Layer 3

**Create configuration module**:
```python
# src/config.py
@dataclass
class BenchmarkConfig:
    cinebench_timeout: int = 600
    stress_test_duration: int = 30

@dataclass
class ThermalConfig:
    watchdog_threshold: float = 95.0
    poll_interval: float = 1.0

config = BenchmarkConfig()  # Load from file if exists
```

**Create fallback strategy**:
```python
# src/fallback.py
class FallbackStrategy:
    def get_llm(self, error: Exception) -> Callable:
        return self.static_proposer
    
    def get_benchmark(self, error: Exception) -> BenchmarkRunner:
        return StressBenchmark()
```

---

## Summary: Refactoring Roadmap

### Priority 1: CRITICAL (Do First)
| Issue | Files | Effort | Impact | Risk |
|-------|-------|--------|--------|------|
| 1.1: Phase dependency contracts | `phases.py`, `base.py`, all phase_*.py | Medium | High | Low |
| 2.1: NVIDIA profile deduplication | `nvidia_profile.py`, `nvidia_profile_setter.py` | Low | Medium | Low |
| 2.3: Unified error handling | All `agent_tools/`, `collectors/` | Medium | High | Medium |

**Estimated effort**: 3-4 days
**Outcome**: More testable, fewer runtime crashes, clearer contracts

### Priority 2: HIGH (Should Do)
| Issue | Files | Effort | Impact | Risk |
|-------|-------|--------|--------|------|
| 1.2: Context field defaults | `phase_baseline.py`, `base.py` | Low | Medium | Low |
| 1.3: LLM global state | `_state.py`, `menu.py`, `phase_config.py` | Low | Medium | Low |
| 1.4: Thermal duplication | `phase_baseline.py`, `phase_final.py`, `thermal_gate.py` | Medium | Medium | Low |
| 2.2: Display mode deduplication | `display_setter.py`, `monitor_dumper.py` | Low | Low | Low |
| 2.4: Missing abstractions | Multiple | Medium | Medium | Low |
| 3.1: Fallback strategy | Multiple | Medium | Medium | Low |
| 3.2: Configuration schema | All files with hardcoded values | Low | Medium | Low |

**Estimated effort**: 4-5 days
**Outcome**: Better maintainability, reduced code duplication, cleaner fallback paths

### Priority 3: MEDIUM (Nice to Have)
| Issue | Files | Effort | Impact | Risk |
|-------|-------|--------|--------|------|
| 1.5: Phase execution visibility | `phases.py` | Low | Low | Low |
| 1.6: Error handling consistency | All phase_*.py | Medium | Low | Low |
| 2.5: Setter interface contract | All setter files, `fix_dispatch.py` | Medium | Medium | Low |
| 3.3: Observability/metrics | All | High | Low | Low |
| 3.4: Lifecycle management | `main.py`, `lhm_sidecar.py`, `phase_*.py` | Medium | Low | Low |
| 3.5: Remove circular import guards | `integrity.py` | Low | Very Low | Low |

**Estimated effort**: 3-4 days
**Outcome**: Better monitoring, cleaner code patterns, improved testability

---

## Verification Strategy

After refactoring, verify:

1. **Unit tests pass** — All 882 existing tests still pass
2. **Integration test** — Run full 5-phase pipeline on test hardware
3. **Error scenarios**:
   - Missing Cinebench → Falls back to stress test ✓
   - LHM unavailable → Skips thermal gate ✓
   - LLM download fails → Uses static templates ✓
   - Phase 3 skips thermal → Phase 5 doesn't crash ✓
4. **Performance** — No measurable slowdown from refactoring

---

## Critical Files Summary

**Orchestration Layer**:
- `/c/1_Coding/2026/lil_bro/src/pipeline/phases.py` (32 lines, orchestrator)
- `/c/1_Coding/2026/lil_bro/src/pipeline/base.py` (48 lines, contracts)
- `/c/1_Coding/2026/lil_bro/src/pipeline/phase_*.py` (×5, ~250 lines total)

**Tools & Collectors**:
- `/c/1_Coding/2026/lil_bro/src/agent_tools/` (×8+ files, ~500 lines)
- `/c/1_Coding/2026/lil_bro/src/collectors/` (×11 files, ~400 lines)

**Infrastructure**:
- `/c/1_Coding/2026/lil_bro/src/utils/` (×11 files, ~771 lines)
- `/c/1_Coding/2026/lil_bro/src/llm/` (×2 files, ~388 lines)
- `/c/1_Coding/2026/lil_bro/src/benchmarks/` (×2 files, ~607 lines)

**Total**: ~4,000 lines across 40+ files

---

## Next Steps

1. **User In-Depth Review** — Detailed feedback on findings and prioritization
2. **Feedback Integration** — Adjust plan based on user preferences
3. **Design Review** — Detailed design for Phase Dependency Framework (Priority 1.1)
4. **Implementation** — Implement Priority 1 issues in order, with unit tests
5. **Integration** — Test against full pipeline
6. **Iteration** — Move to Priority 2 issues

---

**Prepared by**: Code Architecture Analysis (3 Explore agents) + /plan-eng-review
**Location**: `docs/REFACTORING_PLAN.md` and `~/.claude/plans/structured-discovering-whistle.md`
**Status**: Eng review complete — Priority 1 scope reduced and locked

---

## Eng Review Decisions (2026-04-07)

**Scope reduced to Priority 1 (middle ground):** Issues 1.1, 2.1, 2.3 + `config.py` + expand `errors.py`.

| Decision | Choice |
|---|---|
| Scope | Priority 1 only — no PhaseContract, CollectorResult, or FallbackStrategy |
| `calculate_fps_cap` home | Move to `nvidia_profile_dumper.py` (both files already import from there) |
| Error standardization | Add `SetterError(LilBroError)` to `errors.py`; fix `nvidia_profile_setter.py` 3x `RuntimeError` → `SetterError`; keep `display_setter.py` tuple return (dry_run pattern is intentional) |
| `config.py` | Separate `lil_bro_config.json` alongside `.exe`; `config.py` reads it optionally, falls back to defaults |
| Phase 5 guard position | At top of `run()`, before thermal checks |
| Tests | Add `test_phase_final.py` (2 tests) + `test_config.py` (5 tests) + fix 2 regressions |
| TODOs added | T-003 (DEVMODE dedup), T-004 (LLM typing), T-005 (phase status visibility) |

**Implementation files:**
1. `src/pipeline/phase_final.py` — add null guard at top of `run()`
2. `src/collectors/sub/nvidia_profile_dumper.py` — add `calculate_fps_cap()`
3. `src/agent_tools/nvidia_profile.py` — remove local `calculate_fps_cap`, import from dumper
4. `src/agent_tools/nvidia_profile_setter.py` — remove local `calculate_fps_cap`, import from dumper; 3x `RuntimeError` → `SetterError`
5. `src/utils/errors.py` — add `SetterError(LilBroError)`
6. `src/config.py` — new file with `BenchmarkConfig`, `ThermalConfig`, JSON loading
7. `tests/test_phase_final.py` — new file
8. `tests/test_config.py` — new file
9. `tests/test_nvidia_profile.py` — fix 2 regressions (`test_setter_matches_analyzer`, `test_raises_on_import_failure`)

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | ISSUES_OPEN | 9 issues, 2 critical gaps |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**VERDICT:** Ready to implement. 2 critical gaps are test files to write alongside implementation (captured in test plan artifact).
