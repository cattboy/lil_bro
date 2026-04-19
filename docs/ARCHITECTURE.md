# lil_bro — Architecture

## File Tree

```
src/
  main.py                — Thin entry point (integrity, admin, banner, menu; --debug flag via argparse)
  bootstrapper.py        — UAC escalation + Restore Point creation
  _version.py            — Single source of truth for version string
  pipeline/
    __init__.py          — Package marker
    _state.py            — Shared _llm state (get_llm/set_llm)
    base.py              — PipelineContext + Phase protocol for modular phases
    banner.py            — ASCII art banner
    menu.py              — 4-option menu loop (Pipeline, AI Setup, Exit, Revert)
    approval.py          — Proposal display, selection parsing, fix execution, manifest session start
    fix_dispatch.py      — Check->fix dispatch registry (with revert manifest integration)
    phase_revert.py      — Phase 6: Interactive revert flow (menu option 4 or --revert)
    thermal_gate.py      — Pre-benchmark thermal safety check
    phase_bootstrap.py   — Phase 1: Bootstrapping & Safety (UAC, restore point)
    phase_scan.py        — Phase 2: Deep System Scan (collectors, specs JSON)
    phase_baseline.py    — Phase 3: Baseline Benchmark (Cinebench single-core, thermals)
    phase_config.py      — Phase 4: Optimization Configuration Check (all checks, LLM proposals, batch approval)
    phase_final.py       — Phase 5: Final Verification Benchmark (compare delta)
    phases.py            — 5-phase optimization orchestrator + PipelineContext management
    post_run_cleanup.py  — Deletes ./lil_bro/ on exit; preserves CWD-root persistent logs
    startup_thermals.py  — Pre-benchmark thermal safety gate
  collectors/
    spec_dumper.py       — Aggregates all system data into unified JSON
    sub/                 — Individual collectors (WMI, dxdiag, nvidia-smi, EDID, monitor, NVIDIA Profile)
      lhm_sidecar.py     — LibreHardwareMonitor process lifecycle management
      nvidia_profile_dumper.py — NVIDIA Profile Inspector profile extraction + setting ID lookups
  agent_tools/           — Modular system checks (one file per check)
    display.py           — Monitor refresh rate analysis
    display_setter.py    — Applies refresh rate changes via Win32 ChangeDisplaySettingsEx
    game_mode.py         — Windows Game Mode registry
    power_plan.py        — Power plan detection + switching
    xmp_check.py         — RAM XMP/EXPO detection
    rebar.py             — Resizable BAR detection
    temp_audit.py        — Temp folder bloat + cleanup
    mouse.py             — Mouse polling rate
    nvidia_profile.py    — NVIDIA Profile Inspector setting detection + analysis
    nvidia_profile_setter.py — Apply NVIDIA Profile Inspector setting changes
    thermal_guidance.py  — Thermal analysis + pre-benchmark idle safety gate
  llm/                   — LLM integration (optional — tool works without it)
    model_loader.py      — GGUF model loading + first-run download from HuggingFace
    action_proposer.py   — Findings → LLM JSON proposals + static fallback templates
  benchmarks/
    cinebench.py         — BenchmarkRunner: Cinebench auto-detect (12 paths) + CPU stress fallback
    thermal_monitor.py   — Background LHM temperature polling during benchmarks
  utils/
    action_logger.py     — Singleton logger → ./lil_bro_actions.log (CWD root, survives cleanup; echoes to terminal). v2: outcome-tagged entries ([PASS]/[FAIL]/[APPROVED]/[SKIPPED]); log_fix_dispatch/log_fix_result/log_approval_decision helpers; session start/end anchored at app launch in main.py
    debug_logger.py      — Persistent stdlib debug logger → ./lil_bro_debug.log; disabled by default, enabled via --debug flag
    dump_parser.py       — Extracts slim hardware summary from full_specs.json for LLM
    errors.py            — LilBroError, AdminRequiredError, ScannerError, RestorePointError
    formatting.py        — Colorama terminal UI helpers (print_step, print_success, etc.)
    integrity.py         — SHA-256 exe hash verification (frozen builds only)
    paths.py             — Centralized CWD-relative path helper (lil_bro/ runtime dir, persistent log paths)
    platform.py          — Platform detection (IS_WINDOWS) + admin privilege check (is_admin)
    progress_bar.py      — AnimatedProgressBar: plasma-sweep terminal animation during fix execution
    revert.py            — Session manifest I/O (start/append/load, JSON schema v1, session archiving); per-fix revert handlers (power plan, game mode, NVIDIA profile, display); System Restore fallback launcher
    display_utils.py     — Win32 DEVMODE struct + display mode enumeration via ctypes
    subprocess_utils.py  — Centralized subprocess runner with timeout and error handling
    pawnio_check.py      — PawnIO kernel driver installation detection (registry check)
build.py               — Automated build pipeline (5 steps: PawnIO update → lhm-server → PyInstaller → integrity manifest)
lil_bro.spec           — PyInstaller onefile build specification
install_deps.ps1       — One-command dev setup (Python, uv, .NET 8, WDK, submodules)
tools/
  PawnIO/              — PawnIO kernel driver source + WDK build script (fallback path)
  PawnIO_Latest_Check/ — Primary PawnIO.sys source: fetches latest signed binary from namazso/PawnIO.Setup GitHub releases; WDK build is fallback if offline/unavailable
  lhm-server/          — Custom C# thermal sensor server (LibreHardwareMonitorLib + PawnIO)
  nvidiaProfileInspector/ — Bundled NVIDIA Profile Inspector tool (C# WPF app for GPU setting management)
tests/                 — Unit tests, all mocked (no real system modifications)
docs/                  — All progress docs, plans, reports, and notes go here
memory-bank/           — Project design docs (brief, progress, patterns, active context)
```

## Pipeline Architecture

Implemented as modular Phase classes inheriting context via PipelineContext dataclass. Phases 1–5 run automatically during optimization; Phase 6 is a standalone user-triggered revert workflow.

1. **Bootstrap Phase** (`phase_bootstrap.py`) — UAC check, System Restore Point creation
2. **Scan Phase** (`phase_scan.py`) — WMI, dxdiag, nvidia-smi, NVIDIA Profile Inspector, EDID, monitor enum → unified JSON
3. **Baseline Bench Phase** (`phase_baseline.py`) — Cinebench 2026 single-core + thermal baseline
4. **Config Phase** (`phase_config.py`) — All agent_tools checks (display, power, RAM, GPU, thermal, NVIDIA Profile) → LLM proposals (or static fallback) → numbered batch approval UX
5. **Final Phase** (`phase_final.py`) — Re-run benchmark, compare delta vs baseline
6. **Revert Phase** (`phase_revert.py`) — User-triggered via menu option 4 or `--revert`; loads session manifest (`revert.py`), dispatches per-fix revert handlers in reverse order (display → NVIDIA profile → game mode → power plan); falls back to Windows System Restore (`rstrui.exe`) on partial failure. **No additional restore point is created before reverting** — doing so would create a second "lil_bro" restore point and leave the user unable to tell which one to select in `rstrui.exe`. The single restore point created at bootstrap (Phase 1) is the one to use if System Restore is needed.

All phases share state via `PipelineContext` (LHM sidecar, thermal monitor, specs, LLM, benchmark results).

## Tech Stack

| Layer | Tool |
|---|---|
| Language | Python 3.11+ |
| System info | WMI, dxdiag, winreg, nvidia-smi |
| Win32 API | ctypes (EnumDisplaySettings, GetCursorPos, EDID) |
| GPU profiling | nvidia-smi XML output |
| Benchmarking | Cinebench 2026 CLI |
| Thermal monitoring | LibreHardwareMonitor (HTTP API on localhost:8085) |
| Terminal UI | colorama |
| LLM (optional) | llama-cpp-python + Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf |
| Packaging | PyInstaller portable .exe (onefile mode) |
