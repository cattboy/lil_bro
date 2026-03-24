# lil_bro 🎮

A **local, privacy-first AI agent** that optimizes your gaming PC for peak performance.

## What It Does

- 🔍 **Detects misconfigurations** — monitor refresh rates, mouse polling, G-Sync, power plans, XMP/EXPO
- 🧹 **Debloats your system** — clears temp files, old shader caches, disables telemetry hogs
- 🌡️ **Monitors thermals** — real-time CPU/GPU temperature tracking during benchmarks
- 🤖 **AI-powered analysis** — local LLM (Qwen2.5-Coder-7B) reasons about your system and proposes fixes
- 🔒 **100% offline** — no data leaves your device, ever

## Privacy Guarantee

All processing happens locally. The only external calls are optional driver version checks against vendor websites (NVIDIA/AMD/Intel) and the one-time AI model download on first run (skippable).

## Architecture

- **Brain:** `llama-cpp-python` running `Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf` (~4.5 GB, optional — downloaded on first run)
- **Orchestrator:** Python 3.11+
- **Sidecar Tools:** LibreHardwareMonitor (thermal monitoring)
- **Packaging:** PyInstaller portable .exe (Week 4)

## Status

🟢 **Week 6 Complete** — 215 tests passing. Terminal UI redesigned to match DESIGN.md color system. Unicode/ASCII fallback system for non-UTF-8 terminals. Centralized formatting helpers (`print_key_value`, `print_section_divider`, `print_prompt`). Progress bar dynamically sizes to terminal width. All inline colorama removed from main.py and model_loader.py.

Previous: Game Mode auto-fix, animated progress bar, NVIDIA driver display, thermal brand voice, collector resilience, portable .exe packaging, 8 esports checks, Cinebench + thermal benchmarking, LLM-powered recommendations with batch approval UX. LLM is optional — static fallback templates always work offline.

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev environment setup, test commands, and how to build the `.exe`.

See `docs/office-hours-design-20260323.md` for the full product design and roadmap.
