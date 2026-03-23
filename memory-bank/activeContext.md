# Active Context

## Current Work Focus
- **Week 4 packaging in progress** — portable .exe via PyInstaller onefile + integrity check
- All pre-packaging code fixes done: paths relocated to %APPDATA%, freeze_support() added

## Recent Changes (Week 4)
- Created `src/utils/paths.py` — centralized %APPDATA%\lil_bro\ path helper
- Created `src/_version.py` — single source of truth for version string
- Created `src/utils/integrity.py` — SHA-256 exe hash verification (frozen builds only)
- Created `lil_bro.spec` — PyInstaller onefile spec (console, UAC admin, no UPX)
- Created `build.py` — automated build pipeline (PyInstaller + manifest generation)
- Updated `src/utils/action_logger.py` — logs to %APPDATA%\lil_bro\logs\ instead of repo root
- Updated `src/collectors/spec_dumper.py` — specs to %APPDATA%\lil_bro\logs\ instead of repo root
- Updated `src/main.py` — added multiprocessing.freeze_support() + integrity check on startup
- Added `tests/test_paths.py` (6 tests) + `tests/test_integrity.py` (8 tests)
- 164 tests total, all passing

## Next Steps
1. Build the .exe with `python build.py` and smoke test on target machine
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
