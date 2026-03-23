# lil_bro — Claude Code Instructions

## Project Overview

**lil_bro** is a local, privacy-first AI agent for gaming PC optimization. It analyzes system configurations, detects misconfigurations, and applies targeted fixes with user approval. 100% offline — no data leaves the device. The only permitted external calls are driver version checks from vendor websites (NVIDIA/AMD/Intel).

---

## Rules

### Python Environment
- **Always use `uv` for all Python package installs** — never use `pip install` directly.
- **Always activate the `.venv` before running any Python commands.** The venv lives at `.venv/` in the project root.
  - Activate: `.venv/Scripts/activate` (Windows)
  - Create if missing: `uv venv`
  - Install deps: `uv pip install -r requirements.txt`
- Never install packages globally. All dependencies must be inside `.venv/`.

### Documentation
- **Always save progress docs, notes, plans, and reports into `./docs/`** (project root `docs/` folder). Do not scatter docs elsewhere.
- **`docs/vendor-supplied/` contains system-specific reference docs** — consult these before modifying the relevant collectors:
  - `nvidia_smi.txt` — nvidia-smi XML output schema; reference for `get_nvidia_smi()` in `spec_dumper.py`
  - `ami_smi.txt` — AMD SMI output schema; reference for `get_amd_smi()` in `spec_dumper.py`
  - `cinebench.md` — Cinebench CLI flags and result file format; reference for `benchmarks/cinebench.py`

### Safety & User Trust
- Every system modification must call `prompt_approval()` before executing — no silent changes, ever.
- System Restore Point must be created via `bootstrapper.py` before any modifications begin.
- No external HTTP calls, telemetry, or cloud APIs beyond driver version verification URLs.

### Code Architecture
- New system checks belong in `src/agent_tools/` as independent modules.
- Each check function returns a structured dict with at minimum `status` and `message` keys.
- Always implement multi-method fallbacks — never hard-fail when a tool (nvidia-smi, dxdiag, etc.) is missing. Fall back to WMI or registry alternatives.
- Terminal UI only — do not introduce PyQt or GUI dependencies until explicitly requested.

---

## Architecture

```
src/
  main.py              — 5-phase pipeline orchestrator
  bootstrapper.py      — UAC escalation + Restore Point creation
  collectors/
    spec_dumper.py     — Aggregates all system data into unified JSON
    sub/               — Individual collectors (WMI, dxdiag, nvidia-smi, EDID, monitor)
  agent_tools/         — Modular system checks (one file per check)
    display.py         — Monitor refresh rate
    game_mode.py       — Windows Game Mode registry
    power_plan.py      — Power plan detection + switching
    xmp_check.py       — RAM XMP/EXPO detection
    rebar.py           — Resizable BAR detection
    temp_audit.py      — Temp folder bloat + cleanup
    mouse.py           — Mouse polling rate
  benchmarks/
    cinebench.py       — Cinebench 2026 orchestration + thermal monitoring
  utils/
    action_logger.py   — Singleton logger → logs/lil_bro_actions.log
    errors.py          — LilBroError, AdminRequiredError, ScannerError, RestorePointError
    formatting.py      — Colorama terminal UI helpers (print_step, print_success, etc.)
tests/                 — Unit tests, all mocked (no real system modifications)
docs/                  — All progress docs, plans, reports, and notes go here
memory-bank/           — Project design docs (brief, progress, patterns, active context)
```

## 5-Phase Pipeline

1. **Bootstrapping & Safety** — UAC check, Restore Point creation
2. **Deep System Scan** — WMI, dxdiag, nvidia-smi, EDID, monitor enum → unified JSON
3. **Baseline Benchmark** — Cinebench 2026 single-core + thermals
4. **Esports Configuration Check** — All agent_tools checks run, user approves fixes
5. **Final Verification Benchmark** — Re-run benchmark, compare delta

---

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
| LLM (Week 2) | llama-cpp-python + Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf |
| Packaging (Week 4) | PyInstaller + Inno Setup |

---

## Development Roadmap

- **Week 1** ✅ — PoC complete: all esports checks, temp audit, Cinebench, collectors
- **Week 2** — LLM integration: llama-cpp-python, GGUF model loading, JSON action proposals
- **Week 3** — LibreHardwareMonitor full integration, NvidiaProfileInspector export
- **Week 4** — PyInstaller bundle, Inno Setup installer, file-hash verification on launch
