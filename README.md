# lil_bro 🎮

A **local, privacy-first AI agent** that optimizes your gaming PC for peak performance.

## What It Does

- 🔍 **Detects misconfigurations** — monitor refresh rates, mouse polling, G-Sync, power plans, XMP/EXPO, NVIDIA GPU profiles
- 🎮 **Optimizes GPU settings** — NVIDIA Profile Inspector integration for driver-level perf tuning (shader cache, power mgmt, clocks)
- 🧹 **Debloats your system** — clears temp files, old shader caches, disables telemetry hogs
- 🌡️ **Monitors thermals** — real-time CPU/GPU temperature tracking during benchmarks
- 🤖 **AI-powered analysis** — local LLM (Qwen2.5-Coder-7B) reasons about your system and proposes fixes
- ↩️ **One-command revert** — session manifest tracks every change; undo all fixes or fall back to Windows System Restore
- 🔒 **100% offline** — no data leaves your device, ever

## Privacy Guarantee

All processing happens locally. The only external calls are optional driver version checks against vendor websites (NVIDIA/AMD/Intel) and the one-time AI model download on first run (skippable).

## Architecture

- **GUI:** PySide6 desktop app (default); `--terminal` flag restores the original CLI experience
- **Brain:** `llama-cpp-python` running `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` (~4.5 GB, optional — downloaded on first run)
- **Orchestrator:** Python 3.11+
- **Sidecar Tools:** Custom lhm-server.exe (LibreHardwareMonitor + PawnIO for ring-0 thermal access); bundled NVIDIA Profile Inspector (C# WPF for GPU profile editing)
- **Packaging:** PyInstaller portable .exe

## Status

🟢 **v0.2.0.0 — PySide6 Desktop GUI + Pipeline Rescan Idempotency** — Full windowed app with dashboard (live thermals, mouse polling, monitor refresh tiles), optimization pipeline with phase-card progress, batch fix selection dialog, and animated splash screen. Running the pipeline twice in one session now finds nothing the second time. Dashboard "Fix Now" buttons are race-guarded and revertible. CLI mode preserved via `--terminal`. 671 tests passing.

Previous: **v0.1.1.0** — NVIDIA settings no longer falsely flag after a specs reload; Cinebench cleanup, zombie-process kill, and AMD-only NPI init error all fixed. NPI helpers consolidated into `src/utils/nvidia_npi.py`.

Previous: **v0.1.0.0** — Full revert/undo system. Session manifest (`session_latest.json`) records every fix; `phase_revert.py` walks you through reverting each one individually. Windows System Restore fallback offered on partial failure.

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev environment setup, test commands, and how to build the `.exe`.

See `docs/office-hours-design-20260323.md` for the full product design and roadmap.

## Debugging

**GUI mode** always writes `lil_bro_debug.log` (INFO level) to the working directory. Use **Help → Open Debug Log** in the menu bar to open it directly.

**Terminal mode** with `--debug` activates full DEBUG-level logging:
```
lil_bro.exe --terminal --debug
```

**Windowed mode** with `--debug` activates DEBUG-level logging to file (no console):
```
lil_bro.exe --debug
```

Both log files are preserved after each run:
- `lil_bro_actions.log` — audit trail of every system modification lil_bro made
- `lil_bro_debug.log` — process lifecycle, GUI startup, pipeline flow, and exception traces
