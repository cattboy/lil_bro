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

🟢 **Week 5 Complete** — 188 tests passing. Game Mode now auto-fixes via registry write. Animated plasma-sweep progress bar during fix execution. NVIDIA driver version shown after system scan. Thermal idle warnings use brand voice at ≥80°C. Full thermals fallback template for LLM-offline scenarios. Collector resilience: individual failures no longer abort the spec dump.

Previous: portable .exe packaging, 8 esports checks, Cinebench + thermal benchmarking, LLM-powered recommendations with batch approval UX, SHA-256 integrity verification. LLM is optional — static fallback templates always work offline.

## Development

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for dev environment setup, test commands, and how to build the `.exe`.

See `docs/office-hours-design-20260323.md` for the full product design and roadmap.
