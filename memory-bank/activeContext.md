# Active Context

## Current Work Focus
- **Week 7 module split complete** — `main.py` extracted into `src/pipeline/` package (8 modules)
- Branch `feat/week6-terminal-ui` is ready for review/merge; 246 tests, QA health 98/100

## Recent Changes (Week 7)
- Created `src/pipeline/` package: `__init__.py`, `_state.py`, `banner.py`, `menu.py`, `approval.py`, `fix_dispatch.py`, `thermal_gate.py`, `phases.py`
- `src/main.py` trimmed from 549 lines to 48 lines (thin entry point only)
- Dispatch dict pattern: `FIX_REGISTRY: dict[str, Callable[[dict], bool]]` replaces if-elif chain
- Thermal safety gate deduplicated: single `thermal_safety_gate()` function in `thermal_gate.py`
- `_llm` state managed via getter/setter in `_state.py` (avoids Python name-binding bug)
- QA fixes: Callable type annotation (ISSUE-001), `_fix_power_plan` test coverage (ISSUE-002)
- 31 new tests: `test_parse_selection.py` (12), `test_thermal_gate.py` (6), `test_fix_dispatch.py` (13)
- 246 tests total, all passing

## Next Steps
1. Merge `feat/week6-terminal-ui` → `main`
2. Validate llama-cpp-python on RTX 3080 dev machine (hard gate)
3. Benchmark Qwen2.5-3B vs 7B on reference hardware for 60-second SLA

## Active Decisions
- Terminal UI only; PyQt deferred
- LLM is optional — static fallback templates cover all checks
- LHM is optional — thermal checks skipped gracefully if LHM unavailable
- NvidiaProfileInspector deferred to future version

## Important Patterns & Preferences
- Every system modification must require user approval (human-in-the-loop)
- System Restore Point must be created before any changes
- Modular design: each check/fix is an independent, composable module
- LLM proposals fall back to static templates — tool always produces output
- LHM sidecar uses try/finally to guarantee teardown even on crash

## Learnings & Insights
- Dev machine (Intel UHD, no CUDA) can't run LLM inference — LLM-optional design validated
- Static fallback templates are good enough for v1 — LLM adds personality, not critical function
- Batch approval UX ("1 3" / "all" / "skip") is cleaner than per-fix prompting
- LHM sidecar must handle 3 scenarios: already running, port occupied by other app, not installed
