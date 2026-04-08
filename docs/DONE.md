# lil_bro Refactoring — Progress Tracker

**Branch**: `refactor/priority-1-improvements`
**Plan source**: `docs/REFACTORING_PLAN.md`
**Last updated**: 2026-04-08

---

## Completed (Priority 1 + Priority 2-A)

Priority 1 scope (9 files) and Priority 2-A scope (7 files + 2 new test files) are done. 387 tests pass, 0 regressions.

### Issue 1.1 — Phase 5 crashes when Phase 3 was skipped
**Fix**: Null guard at the top of `FinalBenchPhase.run()` before thermal checks.
- `src/pipeline/phase_final.py` — 4-line guard added
- `tests/test_phase_final.py` — 3 new tests (runner=None, thermal gate, happy path)

### Issue 2.1 — calculate_fps_cap duplicated in nvidia_profile.py and nvidia_profile_setter.py
**Fix**: Single canonical definition in `nvidia_profile_dumper.py`; both callers import from there.
- `src/collectors/sub/nvidia_profile_dumper.py` — authoritative `calculate_fps_cap()` added
- `src/agent_tools/nvidia_profile.py` — local definition removed, import updated
- `src/agent_tools/nvidia_profile_setter.py` — local definition removed, import updated
- `tests/test_nvidia_profile.py` — `test_setter_matches_analyzer` → `test_single_canonical_definition`

### Issue 2.3 — RuntimeError raised from setter code with no typed hierarchy
**Fix**: `SetterError(LilBroError)` added to errors.py; 3 raise sites in nvidia_profile_setter.py updated.
- `src/utils/errors.py` — `SetterError` class added
- `src/agent_tools/nvidia_profile_setter.py` — 3x `raise RuntimeError` → `raise SetterError`
- `tests/test_nvidia_profile.py` — `test_raises_on_import_failure` updated to expect `SetterError`

### Issue 3.2 — Thresholds and timeouts hardcoded across multiple files
**Fix**: `src/config.py` with typed dataclasses and optional `lil_bro_config.json` override.
- `src/config.py` — new file: `BenchmarkConfig`, `ThermalConfig`, `AppConfig`, `_load_config()`
- `tests/test_config.py` — 7 new tests (defaults, missing file, valid JSON, malformed, partial, empty)

### Issue 3.2 (config.py) — already listed above under Priority 1.

---

## Completed (Priority 2-A)

### T-004 — Type `PipelineContext.llm` properly
**Fix**: Added `from llama_cpp import Llama` to the `TYPE_CHECKING` block in `base.py`; changed field from `llm: object = None` to `llm: Optional[Llama] = None`.
- `src/pipeline/base.py` — 2-line change (import + annotation)

### Issue 1.2 — Context field defaults unconditionally pre-assigned in phase_baseline.py
**Fix**: Added `_SKIP_RESULT_HOT` named constant; moved the pre-assignment of `ctx.baseline_result` and `ctx.peak_temps` inside the `if benchmark_skipped:` block so the success path no longer overwrites stale sentinel values.
- `src/pipeline/phase_baseline.py` — `_SKIP_RESULT_HOT` added, 2 lines moved inside guard

### Issue 1.4 — Thermal guard pattern duplicated across both benchmark phases
**Fix**: Added `run_thermal_guard(phase_name, ctx, **kwargs) -> bool` combinator to `thermal_gate.py`. Phase 5 now calls this single function instead of two separate checks. Phase 3 retains the two-step explicit pattern to preserve the `ctx.runner is None` sentinel semantics.
- `src/pipeline/thermal_gate.py` — `run_thermal_guard()` added
- `src/pipeline/phase_final.py` — replaced 2-step thermal pattern with `run_thermal_guard`; import updated
- `tests/test_thermal_gate.py` — 4 new tests for `run_thermal_guard`
- `tests/test_phase_final.py` — 2 existing tests updated to patch `run_thermal_guard` (was `require_thermal_protection` / `thermal_safety_gate`)

### T-003 — DEVMODE struct duplicated in monitor_dumper.py and display_setter.py
**Fix**: Single canonical `DEVMODE` struct and `enum_raw_modes()` in `src/utils/display_utils.py`; both callers import from there.
- `src/utils/display_utils.py` — new file: `DEVMODE`, `enum_raw_modes()`, constants
- `src/collectors/sub/monitor_dumper.py` — local DEVMODE removed; imports from display_utils; `enum_display_modes()` delegates to `enum_raw_modes`
- `src/agent_tools/display_setter.py` — local DEVMODE and `_enum_all_modes()` removed; imports from display_utils; `find_best_mode()` uses `enum_raw_modes`
- `tests/test_display_utils.py` — new file: 5 tests (struct fields, constants, single canonical definition)

---

## Outstanding

### Priority 2 (Should Do)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| 1.3 | LLM stored as `object` in global `_state.py` — untestable, weakly typed | `_state.py`, `menu.py`, `phase_config.py` | S |
| 2.4 | No CollectorResult type, no unified subprocess wrapper, no specs schema | Multiple | M |
| 3.1 | Fallback logic scattered — LLM, Cinebench, model, thermal each have separate ad-hoc fallback paths | Multiple | M |

### Priority 3 (Nice to Have)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| 1.5 | Phase execution status not visible to orchestrator — no ran/skipped/failed signal | `phases.py` | S |
| 1.6 | Error handling inconsistent across phases — some catch, some don't | All `phase_*.py` | M |
| 2.5 | Setter interface contract missing — each setter has a different signature | All setter files, `fix_dispatch.py` | M |
| 3.3 | Observability/metrics missing — no timing, no success ratio, no aggregation | N/A | L |
| 3.4 | Lifecycle management split — LHM and ThermalMonitor ownership unclear | `main.py`, `lhm_sidecar.py`, `phase_*.py` | M |
| 3.5 | Circular import guard in integrity.py (lazy import to avoid cycle) | `integrity.py` | XS |
| T-001 | Future-proof formatting.py for GUI backend (see TODOS.md) | `formatting.py` | M |
| T-002 | Harden LLM output against UnicodeEncodeError on Windows CMD (see TODOS.md) | `formatting.py` | S |
| T-005 | Phase.run() return PhaseResult instead of None (see TODOS.md) | `phases.py`, all `phase_*.py` | S |

---

## Explicitly Out of Scope (decisions from eng-review)

- **Setter interface Protocol** — `display_setter.py`'s `(bool, str)` return is intentional (dry_run/apply two-phase pattern). Not changing.
- **Phase Dependency Framework** (PhaseContract/PhaseResult classes) — over-engineered for a 4,000-line solo tool. Null guard in phase_final.py is sufficient.
- **Unified CollectorResult generic type** — deferred to Priority 2 if/when the codebase grows.
- **FallbackStrategy Protocol** — deferred; individual fallback paths work and are tested.
