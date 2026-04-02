# Active Context

## Current Work Focus
- **Sprint pawnio-cleanup** — Build pipeline hardened; `update_pawnio.ps1` promoted to primary PawnIO.sys acquisition path
- Branch `sprint/pawnio-cleanup`

## Recent Changes (pawnio-cleanup)
- `build.py`: added `run_pawnio_update()` function; runs `tools/PawnIO_Latest_Check/update_pawnio.ps1` as step [2/5] before lhm-server build
- Build steps renumbered 4→5; module docstring updated with step breakdown
- `CLAUDE.md`: architecture entry for `build.py` and `tools/PawnIO*` entries updated to reflect primary/fallback distinction
- PawnIO.sys acquisition priority: GitHub signed binary (update_pawnio.ps1) → WDK source compile (tools/PawnIO/build.ps1) → embed skipped

## Next Steps
1. Validate llama-cpp-python on RTX 3080 dev machine (hard gate)
2. Benchmark Qwen2.5-3B vs 7B on reference hardware for 60-second SLA

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
