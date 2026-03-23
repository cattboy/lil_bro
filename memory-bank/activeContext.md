# Active Context

## Current Work Focus
- **Week 2 LLM integration complete** — model loader, action proposer, batch approval UX
- Full design doc written: `docs/office-hours-design-20260323.md`
- LLM is optional — menu option 2 for setup, pipeline uses static fallback without it

## Recent Changes
- Added `src/llm/` module (model_loader.py, action_proposer.py)
- Rewrote `src/main.py` Phase 4 with numbered proposal list + batch selection
- Added 3-option menu: pipeline, AI model setup, exit
- 20 new tests in `tests/test_action_proposer.py` (69/69 total passing)
- Uncommented `llama-cpp-python` in requirements.txt

## Next Steps
1. Validate llama-cpp-python on RTX 3080 dev machine (hard gate deferred from current machine)
2. Benchmark Qwen2.5-3B vs 7B on reference hardware for 60-second SLA
3. LibreHardwareMonitor deep integration — launch as sidecar, poll `/data.json` (Week 3)
4. Thermal guidance module — Cinebench peak temps → LLM guidance (Week 3)
5. PyInstaller bundling + Inno Setup installer (Week 4)

## Active Decisions
- Terminal UI only; PyQt deferred
- LLM is optional — static fallback templates cover all 7 checks
- Model choice: `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` (pending 3B vs 7B benchmark)
- NvidiaProfileInspector deferred to future version
- Model downloaded on first run from HuggingFace, cached in `%APPDATA%\lil_bro\models\`

## Important Patterns & Preferences
- Every system modification must require user approval (human-in-the-loop)
- System Restore Point must be created before any changes
- Modular design: each check/fix is an independent, composable module
- LLM proposals fall back to static templates — tool always produces output

## Learnings & Insights
- Dev machine (Intel UHD, no CUDA) can't run LLM inference — LLM-optional design validated
- Static fallback templates are good enough for v1 — LLM adds personality, not critical function
- Batch approval UX ("1 3" / "all" / "skip") is cleaner than per-fix prompting
