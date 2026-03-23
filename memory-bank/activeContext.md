# Active Context

## Current Work Focus
- **Week 3 LHM + thermal integration** — sidecar manager, thermal monitor, thermal guidance
- LHM launches as background process in Phase 2, temps sampled during Cinebench in Phase 3
- Thermal guidance added to Phase 4 findings (CPU >85°C / GPU >90°C thresholds)

## Recent Changes
- Added `src/collectors/sub/lhm_sidecar.py` — LHM process lifecycle (port probe, launch, teardown)
- Added `src/benchmarks/thermal_monitor.py` — background thread polls LHM during benchmark
- Added `src/agent_tools/thermal_guidance.py` — threshold analysis + plain-English guidance
- Updated `src/collectors/sub/libra_hm_dumper.py` — uses shared LHM_URL constant
- Updated `src/main.py` — LHM sidecar in Phase 2, thermal polling in Phase 3/5, guidance in Phase 4
- Added `__init__.py` to `collectors/`, `collectors/sub/`, `benchmarks/`
- 43 new tests across 3 test files (112/112 total passing)

## Next Steps
1. Validate llama-cpp-python on RTX 3080 dev machine (hard gate deferred from current machine)
2. Benchmark Qwen2.5-3B vs 7B on reference hardware for 60-second SLA
3. PyInstaller bundling + Inno Setup installer (Week 4)

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
