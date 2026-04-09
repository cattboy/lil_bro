---
name: refactoring_status
description: Current refactoring branch status — outstanding Priority 2 items and explicitly deferred work
type: project
---

# Refactoring Status

**Branch**: `refactor/priority-1-improvements`  
**Plan**: `docs/REFACTORING_PLAN.md`  
**Progress log**: `docs/DONE.md`

## Outstanding Priority 2 (not yet started)

- **Issue 2.4**: Subprocess wrapper + specs schema validation (M effort)
- **Issue 3.1**: Fallback strategy (M effort — likely deferred per eng review)

## Explicitly out of scope — do not re-propose

These were deliberately rejected or deferred in engineering review:

| Item | Decision |
|---|---|
| Setter interface Protocol | display_setter tuple return is intentional |
| PhaseContract / PhaseResult framework | over-engineered for current needs |
| FallbackStrategy Protocol | individual fallback paths work; deferred |
| Unified CollectorResult generic type | deferred |

## Completed (Priority 1 + 2-A) — reference only

- Issue 1.1: Phase 5 null guard for `ctx.runner`
- Issue 1.2: `_SKIP_RESULT_HOT` constant; ctx fields moved inside guard in `phase_baseline.py`
- Issue 1.3: LLM type annotations in `_state.py`, `phases.py`, `action_proposer.py`
- Issue 1.4: `run_thermal_guard()` combinator in `thermal_gate.py`; `phase_final.py` uses it
- Issue 2.1: `calculate_fps_cap()` canonical in `nvidia_profile_dumper.py`
- Issue 2.3: `SetterError` added to `errors.py`; `RuntimeError` → `SetterError` in `nvidia_profile_setter.py`
- Issue 3.2: `src/config.py` with `BenchmarkConfig`, `ThermalConfig`, `AppConfig` + JSON override
- T-003: `DEVMODE` + `enum_raw_modes()` canonical in `display_utils.py`
- T-004: `PipelineContext.llm` typed as `Optional[Llama]` in `base.py`
