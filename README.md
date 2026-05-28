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

## Status

🟢 **v0.2.0.0 — PySide6 Desktop GUI + Pipeline Rescan Idempotency** — Full windowed app with dashboard (live thermals, mouse polling, monitor refresh tiles), optimization pipeline with phase-card progress, batch fix selection dialog, and animated splash screen. Running the pipeline twice in one session now finds nothing the second time. Dashboard "Fix Now" buttons are race-guarded and revertible. CLI mode preserved via `--terminal`. 671 tests passing.

## How to Run

1. **Download** `lil_bro.exe` from [Releases](https://github.com/anthropics/lil_bro/releases)
2. **Double-click** the `.exe` to launch
   - A **UAC (User Access Control) prompt** will appear — this is expected and required. lil_bro needs admin privileges to analyze and modify system settings.
3. **Follow the on-screen prompts** — the app will analyze your system and propose optimizations
4. **Review and approve** fixes before they're applied

### CLI Mode (Terminal)

For a command-line interface instead of the graphical app:
```
lil_bro.exe --terminal
```

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

## Further Reading

- **[DEVELOPMENT.md](DEVELOPMENT.md)** — Architecture, developer setup, test commands, and build instructions
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to report bugs, submit pull requests, and contribute
