# Architecture Decisions (from Eng Review 2026-04-07)

## Refactoring branch: `refactor/priority-1-improvements`
Plan: `docs/REFACTORING_PLAN.md` | Progress: `docs/DONE.md`

## Completed (Priority 1 + 2-A)
- Issue 1.1: Phase 5 null guard for ctx.runner
- Issue 2.1: calculate_fps_cap() canonical in nvidia_profile_dumper.py
- Issue 2.3: SetterError added to errors.py; RuntimeError → SetterError in nvidia_profile_setter.py
- Issue 3.2: src/config.py with BenchmarkConfig, ThermalConfig, AppConfig + JSON override
- T-004: PipelineContext.llm typed as Optional[Llama] in base.py
- Issue 1.2: _SKIP_RESULT_HOT constant; ctx fields moved inside guard in phase_baseline.py
- Issue 1.4: run_thermal_guard() combinator in thermal_gate.py; phase_final.py uses it
- T-003: DEVMODE + enum_raw_modes() canonical in display_utils.py

## Key patterns
- Human-in-the-loop: every fix calls prompt_approval() before executing
- Graceful degradation: always fall back when tool missing (LHM, Cinebench, LLM)
- Temp files in CWD via get_temp_dir() — never %TEMP%
