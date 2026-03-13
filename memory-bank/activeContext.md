# Active Context

## Current Work Focus
- **Project initialization** — memory bank setup, project scaffolding
- Ready to begin Phase 1 (Week 1 PoC) implementation

## Recent Changes
- Created memory-bank with all core files from project brief
- Established project structure under `c:\1_Coding\1_lil_bro`

## Next Steps
1. Scaffold the Python project structure inside `src/` (Completed)
2. Implement Phase 1 / Week 1 PoC:
   - System Restore Point creation via PowerShell (Completed)
   - Monitor refresh rate and Mouse polling rate (Completed)
   - 'Esports Check' modules: Game Mode, Power Plan, XMP/EXPO (Completed)
   - Temp folder size audit (Completed)
3. Proceed to "Speed Up My PC" (ReAct Loop) implementation:
   - Benchmark orchestration
   - Debloating engine
4. Set up `llama-cpp-python` integration (Week 2)
4. Integrate LibreHardwareMonitor for thermal readings (Week 3)
5. Package with PyInstaller + Inno Setup (Week 4)

## Active Decisions
- Starting with terminal UI; PyQt GUI deferred to later phase
- Model choice: `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` — good balance of size and capability
- Privacy-first: only external call allowed is driver version verification from vendor websites

## Important Patterns & Preferences
- Every system modification must require user approval (human-in-the-loop)
- System Restore Point must be created before any changes
- Modular design: each check/fix is an independent, composable module

## Learnings & Insights
- Project is brand new — no code written yet, `src/` directory is empty
- Project brief is comprehensive and well-structured with a 4-week roadmap
