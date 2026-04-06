# lil_bro — Claude Code Instructions

## Project Overview

**lil_bro** is a local, privacy-first AI agent for gaming PC optimization. It analyzes system configurations, detects misconfigurations, and applies targeted fixes with user approval. 100% offline — no data leaves the device. The only permitted external calls are driver version checks from vendor websites (NVIDIA/AMD/Intel) and the one-time GGUF model download from HuggingFace on first run.

---

## Rules

### Python Environment
- **Always use `uv` for all Python package installs** — never use `pip install` directly.
- **Always activate the `.venv` before running any Python commands.** The venv lives at `.venv/` in the project root.
  - Activate: `.venv/Scripts/activate` (Windows)
  - Create if missing: `uv venv`
  - Install deps: `uv pip install -e ".[dev]"`
  - Install with LLM support: `uv pip install -e ".[dev,llm]"`
- Never install packages globally. All dependencies must be inside `.venv/`.
- `requirements.txt` has been removed — `pyproject.toml` is the single source of truth for all dependencies.

### Documentation
- **Always save progress docs, notes, plans, and reports into `./docs/`** (project root `docs/` folder). Do not scatter docs elsewhere.
- **`docs/vendor-supplied/` contains system-specific reference docs** — consult these before modifying the relevant collectors:
  - `nvidia_smi.txt` — nvidia-smi XML output schema; reference for `get_nvidia_smi()` in `spec_dumper.py`
  - `ami_smi.txt` — AMD SMI output schema; reference for `get_amd_smi()` in `spec_dumper.py`
  - `cinebench.md` — Cinebench CLI flags and result file format; reference for `benchmarks/cinebench.py`

### Safety & User Trust
- Every system modification must call `prompt_approval()` before executing — no silent changes, ever.
- System Restore Point must be created via `bootstrapper.py` before any modifications begin.
- No external HTTP calls, telemetry, or cloud APIs beyond driver version verification URLs and the one-time model download from HuggingFace.

### Code Architecture
- New system checks belong in `src/agent_tools/` as independent modules.
- Each check function returns a structured dict with at minimum `status` and `message` keys.
- Always implement multi-method fallbacks — never hard-fail when a tool (nvidia-smi, dxdiag, etc.) is missing. Fall back to WMI or registry alternatives.
- Terminal UI only — do not introduce PyQt or GUI dependencies until explicitly requested.

### Subprocess & Temp Files
- **All subprocess temp files must be stored in CWD, not `%TEMP%`.** Use `get_temp_dir()` from `src/utils/paths.py` as the `dir=` argument for `tempfile.TemporaryDirectory()` and `tempfile.mkstemp()`. This ensures all runtime artifacts live under `./lil_bro/` and get cleaned up on exit via `post_run_cleanup.py`.
- Any new code spawning subprocesses that produce temp files must use `dir=str(get_temp_dir())` — never rely on the system default temp directory.
- PyInstaller's `runtime_tmpdir='.'` in `lil_bro.spec` ensures `_MEI*` extraction dirs are created in CWD. Stale `_MEI*` dirs from crashes are cleaned up by `_cleanup_stale_mei()` in `post_run_cleanup.py`.

---

## Architecture

```
src/
  main.py                — Thin entry point (integrity, admin, banner, menu; --debug flag via argparse)
  bootstrapper.py        — UAC escalation + Restore Point creation
  _version.py            — Single source of truth for version string
  pipeline/
    __init__.py          — Package marker
    _state.py            — Shared _llm state (get_llm/set_llm)
    banner.py            — ASCII art banner
    menu.py              — 3-option menu loop + AI model setup
    approval.py          — Proposal display, selection parsing, fix execution
    fix_dispatch.py      — Check->fix dispatch registry
    thermal_gate.py      — Pre-benchmark thermal safety check
    phases.py            — 5-phase pipeline orchestrator
    post_run_cleanup.py  — Deletes ./lil_bro/ on exit; preserves CWD-root persistent logs
  collectors/
    spec_dumper.py       — Aggregates all system data into unified JSON
    sub/                 — Individual collectors (WMI, dxdiag, nvidia-smi, EDID, monitor)
      lhm_sidecar.py    — LibreHardwareMonitor process lifecycle management
  agent_tools/           — Modular system checks (one file per check)
    display.py           — Monitor refresh rate analysis
    display_setter.py    — Applies refresh rate changes via Win32 ChangeDisplaySettingsEx
    game_mode.py         — Windows Game Mode registry
    power_plan.py        — Power plan detection + switching
    xmp_check.py         — RAM XMP/EXPO detection
    rebar.py             — Resizable BAR detection
    temp_audit.py        — Temp folder bloat + cleanup
    mouse.py             — Mouse polling rate
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
    progress_bar.py      — AnimatedProgressBar: plasma-sweep terminal animation during fix execution
build.py               — Automated build pipeline (5 steps: PawnIO update → lhm-server → PyInstaller → integrity manifest)
lil_bro.spec           — PyInstaller onefile build specification
install_deps.ps1       — One-command dev setup (Python, uv, .NET 8, WDK, submodules)
tools/
  PawnIO/              — PawnIO kernel driver source + WDK build script (fallback path)
  PawnIO_Latest_Check/ — Primary PawnIO.sys source: fetches latest signed binary from namazso/PawnIO.Setup GitHub releases; WDK build is fallback if offline/unavailable
  lhm-server/          — Custom C# thermal sensor server (LibreHardwareMonitorLib + PawnIO)
tests/                 — Unit tests, all mocked (no real system modifications)
docs/                  — All progress docs, plans, reports, and notes go here
memory-bank/           — Project design docs (brief, progress, patterns, active context)
```

## 5-Phase Pipeline

1. **Bootstrapping & Safety** — UAC check, Restore Point creation
2. **Deep System Scan** — WMI, dxdiag, nvidia-smi, EDID, monitor enum → unified JSON
3. **Baseline Benchmark** — Cinebench 2026 single-core + thermals
4. **Esports Configuration Check** — All agent_tools checks run → LLM proposals (or static fallback) → numbered batch approval UX
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
| LLM (optional) | llama-cpp-python + Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf |
| Packaging (Week 4) | PyInstaller portable .exe (onefile mode) |

---

## Development Roadmap

- **Week 1** ✅ — PoC complete: all esports checks, temp audit, Cinebench, collectors
- **Week 2** ✅ — LLM integration: model loader, action proposer, batch approval UX, static fallback
- **Week 3** ✅ — LHM sidecar, thermal monitor, thermal guidance, benchmark runner rework, pre-benchmark safety gate
- **Week 4** ✅ — PyInstaller portable .exe, %APPDATA% path relocation, SHA-256 integrity verification
- **Week 5** ✅ — Game Mode auto-fix, thermals fallback template, brand voice idle warning, animated progress bar, NVIDIA driver display, expanded test coverage (188 tests), collector resilience via `_safe_collect`
- **Week 6** ✅ — Terminal UI redesign: DESIGN.md color system compliance, Unicode/ASCII fallback system, centralized formatting helpers (print_key_value, print_section_divider, print_prompt), dynamic progress bar width, inline colorama removal, 27 new tests (215 total)
- **Week 7** ✅ — main.py module split: extracted `src/pipeline/` package (banner, menu, approval, fix_dispatch, thermal_gate, phases, _state), dispatch dict pattern, deduped thermal gate, 27 new tests (242 total)
- **Week 8** ✅ — Bundle thermal sensor server: custom C# lhm-server.exe (LibreHardwareMonitorLib, PawnIO-era v0.9.*), HTTP /data.json sidecar; lhm_sidecar.py tuple return + custom vs full-LHM launch logic; fix CPU sensor derivation (_derive_cpu_temp priority: CPU Package → Tctl/Tdie → safe CPU; AMD Ryzen support; excludes hotspot/VRM/Core Max); 22 new tests (264 total)
- **Sprint: pawnio-cleanup** ✅ — Build pipeline hardened: `update_pawnio.ps1` integrated as build step [2/5]; fetches latest signed PawnIO.sys from namazso/PawnIO.Setup GitHub releases; WDK source compilation retained as fallback. Debug logging: `debug_logger.py` singleton + `--debug` CLI flag (disabled by default, no overhead); `get_specs_path()` fixed to `./lil_bro/full_specs.json`; `post_run_cleanup.py` cleans `./lil_bro/` on exit while preserving CWD-root logs; 312 tests passing
- **Sprint: action-logger-tuning** ✅ — Action logger v2: `outcome` param on `log_action()` for programmatic parsing; `log_fix_dispatch/log_fix_result/log_approval_decision` helpers; fix dispatch and approval flow fully instrumented; session start/end moved to `main.py` to capture full app lifecycle (including startup LHM sidecar); 325 tests passing

---

## Design System
Always read `DESIGN.md` before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

---

## gstack Design Docs

When any gstack skill is invoked (`/office-hours`, `/plan-eng-review`, `/plan-ceo-review`, `/plan-design-review`, `/autoplan`, `/review`, `/ship`, etc.), **always check `C:\Users\Owner\.gstack\projects\cattboy-lil_bro\` for prior design docs** before starting work.

Design docs from `/office-hours` sessions are stored there as:
`{user}-{branch}-design-{datetime}.md`

These docs contain approved architecture decisions, rejected approaches, feasibility risks, and open questions that should inform all downstream planning and implementation work. Downstream skills (plan-eng-review, plan-ceo-review, etc.) auto-discover these docs — but Claude Code should also read the most recent approved doc when beginning any significant feature work.

List available docs with:
```bash
ls -t C:/Users/Owner/.gstack/projects/cattboy-lil_bro/*.md 2>/dev/null
```
