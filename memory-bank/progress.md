# Progress

## What Works
- ✅ Project brief defined with clear scope and 4-phase architecture
- ✅ Memory bank initialized with all core files

## What's Left to Build

### Phase 1: Architecture & Packaging
- [x] Python project scaffolding (`src/` structure)
- [x] PyInstaller portable .exe bundling (`lil_bro.spec` + `build.py`)
- [x] Initial run file-hash verification (`src/utils/integrity.py`)
- [x] Writable paths relocated to `%APPDATA%\lil_bro\` (`src/utils/paths.py`)

### Phase 2: Bootstrapping & System Safety
- [x] UAC privilege escalation
- [x] System Restore Point creation (PowerShell)
- [x] Deep scan: `dxdiag` output capture (`collectors/sub/dxdiag_dumper.py`)
- [ ] Deep scan: NvidiaProfileInspector export (deferred — no v1 auto-fix needs it)
- [x] Deep scan: LibreHardwareMonitor sidecar launch + baseline logging

### Phase 3: Feature Modules
#### Configuration Check ("Optimization Check")
- [x] Monitor refresh rate detection (WMI + EDID)
- [x] Mouse polling rate detection (`GetMouseMovePointsEx`)
- [x] Windows Game Mode check (registry)
- [x] Power plan check (Ultimate Performance)
- [x] XMP/EXPO detection (WMI memory speed)
- [x] Resizable BAR (ReBAR) detection (WMI memory range)

#### Speed Up My PC (ReAct Loop)
- [x] Benchmark orchestration — BenchmarkRunner with Cinebench auto-detection (12 paths) + CPU stress fallback (multiprocessing)
- [x] Pre-benchmark thermal safety gate — idle temp check before stressing system (CPU ≥75°C / GPU ≥80°C = warning)
- [ ] Debloating engine (temp cleanup, NVIDIA profile tweaks, service disabling)
- [x] Thermal verification & guidance (LibreHardwareMonitor integration)

### Phase 4: LLM Integration
- [x] `llama-cpp-python` wrapper (`src/llm/model_loader.py`)
- [x] GGUF model loading and inference (CPU-only, first-run download from HuggingFace)
- [x] JSON action proposal generation (`src/llm/action_proposer.py` + static fallback)
- [x] Human-in-the-loop batch approval flow (numbered proposals, "1 3" / "all" / "skip")

### Phase 5: UI & Polish
- [ ] Terminal-based interactive UI
- [ ] Optional PyQt GUI
- [ ] Friendly LLM-generated explanations

## Current Status
🟢 **Week 8 + pawnio-cleanup complete** — lhm-server.exe bundled with PawnIO.sys (custom C# thermal server). Build pipeline now has 5 steps: [1] clean, [2] fetch signed PawnIO.sys from GitHub (update_pawnio.ps1), [3] build lhm-server, [4] PyInstaller, [5] manifest. WDK source build is the automatic fallback when offline/unavailable. 264 tests passing.

## Known Issues
- llama-cpp-python not yet tested with PyInstaller bundling (hard gate deferred to RTX 3080 dev machine)
- Qwen2.5-7B vs 3B model size decision pending SLA benchmark on reference hardware

## Evolution of Decisions
| Date | Decision | Context |
|------|----------|---------|
| 2026-03-13 | Project created | Memory bank initialized from project brief |
| 2026-03-13 | Terminal UI first | PyQt deferred; start simple, upgrade later |
| 2026-03-13 | Qwen2.5-Coder-7B model | Best balance of size (~4.5 GB) and capability for offline use |
| 2026-03-23 | LLM made optional | Tool works with static fallback templates; menu option 2 for model setup |
| 2026-03-23 | NvidiaProfileInspector deferred | No v1 auto-fix requires GPU profile changes |
| 2026-03-23 | Staged model download | Installer ships without GGUF; first-run download from HuggingFace |
| 2026-03-23 | LHM sidecar + thermal monitoring | Full pipeline: sidecar launch, background temp polling during Cinebench, thermal guidance in Phase 4 |
| 2026-03-23 | Pre-benchmark thermal gate | Idle temp check before benchmark; CPU ≥75°C / GPU ≥80°C = warn and offer to skip |
| 2026-03-23 | BenchmarkRunner replaces CinebenchOrchestrator | Cinebench auto-detect (12 paths) + CPU stress fallback via multiprocessing when not installed |
| 2026-03-23 | RawValue sensor parsing | LHM JSON parser prefers numeric RawValue over string Value — more robust across locales |
| 2026-03-24 | Game Mode auto-fix via registry | Replaced manual instruction with direct registry write (AutoGameModeEnabled) |
| 2026-03-24 | _safe_collect in spec_dumper | Wrap each collector independently so one failure (e.g. nvidia-smi missing) doesn't abort the full dump |
| 2026-03-24 | requirements.txt removed | pyproject.toml is now single source of truth; llama-cpp-python moved to optional [llm] extra |
| 2026-03-24 | CONTRIBUTING.md added | Standard practice: README stays user-facing, CONTRIBUTING has dev setup + build commands |
| 2026-03-30 | GitHub-first PawnIO.sys acquisition | update_pawnio.ps1 integrated into build.py step [2/5]; downloads official signed binary from namazso/PawnIO.Setup; WDK source build demoted to fallback |
| 2026-04-01 | Multi-arch PawnIO extraction deferred | All 4 variants (2× x64, 2× ARM64) exist in the CAB; currently only x64 is kept. Backlog item in docs/todos.md covers preserving all arch variants + build.py --arch flag for future ARM64 builds |
