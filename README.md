# lil_bro 🎮

A **local, privacy-first AI agent** that optimizes your gaming PC for peak performance.

## What It Does

- 🔍 **Detects misconfigurations** — monitor refresh rates, mouse polling, G-Sync, power plans, XMP/EXPO, NVIDIA GPU profiles
- 🎮 **Optimizes GPU settings** — NVIDIA Profile Inspector integration for driver-level perf tuning (shader cache, power mgmt, clocks)
- 🧹 **Debloats your system** — clears temp files, old shader caches, disables telemetry hogs
- 🌡️ **Monitors thermals** — real-time CPU/GPU temperature tracking during benchmarks
- 🤖 **AI-powered analysis** — local LLM (Qwen2.5-Coder-7B) reasons about your system and proposes fixes
- 🔒 **100% offline** — no data leaves your device, ever

## Privacy Guarantee

All processing happens locally. The only external calls are optional driver version checks against vendor websites (NVIDIA/AMD/Intel) and the one-time AI model download on first run (skippable).

## Architecture

- **Brain:** `llama-cpp-python` running `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` (~4.5 GB, optional — downloaded on first run)
- **Orchestrator:** Python 3.11+
- **Sidecar Tools:** Custom lhm-server.exe (LibreHardwareMonitor + PawnIO for ring-0 thermal access); bundled NVIDIA Profile Inspector (C# WPF for GPU profile editing)
- **Packaging:** PyInstaller portable .exe

## Status

🟢 **v0.10.0 — Sprint: nvidia-profile-inspector** — 882 tests passing. Bundled NVIDIA Profile Inspector tool (C# WPF) with Python integration: nvidia_profile_dumper.py extracts GPU profiles; nvidia_profile.py detects misconfigs; nvidia_profile_setter.py applies fixes. Pipeline refactored into Phase classes (base.py + 5 phase modules) with PipelineContext state bag for cleaner orchestration. Setting ID validation against NPI_CustomSettingNames.xml canonical reference.

Previous: Action logger v2 with outcome tags (`[PASS]`/`[FAIL]`/`[APPROVED]`/`[SKIPPED]`); session lifecycle anchored at app launch including startup LHM sidecar. Debug logging via `--debug` flag. Post-run cleanup deletes `./lil_bro/` while preserving CWD-root logs.

Previous: `main.py` split into `src/pipeline/` package. Dispatch dict pattern. Terminal UI redesigned to DESIGN.md. Unicode/ASCII fallback. Game Mode auto-fix, animated progress bar, Cinebench + thermal benchmarking, LLM-powered recommendations with batch approval UX. LLM is optional — static fallback templates always work offline.

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev environment setup, test commands, and how to build the `.exe`.

See `docs/office-hours-design-20260323.md` for the full product design and roadmap.
