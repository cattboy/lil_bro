# Development Guide

This guide covers everything you need to develop, test, and build lil_bro locally.

---

## Requirements

- **Python 3.11+** (3.13 tested)
- **uv** — fast Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **Windows 10/11** — this tool is Windows-only (uses WMI, winreg, ctypes Win32 APIs)
- **.NET 8 SDK** — required to build the bundled `lhm-server.exe` thermal sensor sidecar

### Installing .NET 8 SDK (winget)

The fastest way on Windows 10/11 is via winget:

```powershell
winget install Microsoft.DotNet.SDK.8
```

To verify the install or check what SDK versions are present:

```powershell
dotnet --list-sdks
```

You need at least one `8.x.xxx` entry. The SDK includes all runtimes — no separate runtime install is needed.

> **Note:** If you only need to run the pre-built `lhm-server.exe` (already included in `tools/lhm-server/`), you do not need the SDK. The SDK is only required if you want to rebuild the sidecar from source.

---

## Setup

```bash
# Create the virtual environment
uv venv

# Activate it (PowerShell or Git Bash)
.venv/Scripts/activate

# Install runtime + dev deps
uv pip install -e ".[dev]"

# Optional: also install LLM support (llama-cpp-python, ~4.5 GB model download on first run)
uv pip install -e ".[dev,llm]"
```

All dependencies are defined in `pyproject.toml`. Never use `pip install` directly.

**One-command setup** (installs Python, uv, .NET 8 SDK, WDK, and initializes submodules):

```powershell
powershell -ExecutionPolicy Bypass -File install_deps.ps1
```

---

## Running the tool

```bash
# From the project root, with venv active:
python -m src.main
```

Or use the entry point registered by pyproject.toml:

```bash
lil_bro
```

To enable debug logging (writes `./lil_bro_debug.log` at CWD root):

```bash
python -m src.main --debug
# or, for the built exe:
lil_bro.exe --debug
```

---

## Running tests

All tests are mocked — no real system modifications, no hardware required.

```bash
# Full suite
python -m pytest tests/ -v

# Single module
python -m pytest tests/test_game_mode.py -v

# With coverage (if pytest-cov installed)
python -m pytest tests/ --cov=src --cov-report=term-missing
```

Current suite: **671 tests**, all passing.

---

## Building the portable .exe

The build pipeline uses PyInstaller. Output lands in `dist/lil_bro.exe`.

```bash
# Full build + SHA-256 integrity manifest
python build.py

# Clean previous build artifacts first, then build
python build.py --clean
```

`build.py` does the following automatically:
1. *(Optional)* Cleans previous `dist/` and `build/` artifacts when `--clean` is passed
2. Fetches the latest signed `PawnIO.sys` from namazso/PawnIO.Setup GitHub releases (falls back to WDK source build if offline or 7-Zip is absent)
3. Builds `lhm-server.exe` via `tools/lhm-server/build.ps1` (embeds PawnIO.sys)
4. Runs `PyInstaller lil_bro.spec --noconfirm`
5. Generates `dist/integrity.json` with the SHA-256 hash of the exe

The `.spec` file (`lil_bro.spec`) is the PyInstaller build configuration — edit it if you need to add data files or hidden imports.

**Note:** `llama-cpp-python` has not been fully validated under PyInstaller bundling yet. Test on target hardware before distributing a build with LLM support.

---

## PawnIO driver (thermal sensor access)

lhm-server.exe uses LibreHardwareMonitorLib to read CPU/GPU temperatures. On modern Windows, ring-0 hardware access requires the **PawnIO kernel driver**. The driver is embedded inside lhm-server.exe and auto-installed on first admin launch.

### Signed vs. unsigned PawnIO.sys

PawnIO.sys is a **kernel driver** — Windows enforces strict code-signing requirements:

| Build type | Source | Loads without test-signing? |
|---|---|---|
| Official release | [pawnio.eu](https://pawnio.eu) | Yes (WHQL-signed) |
| Built from source | `tools/PawnIO/build.ps1` | **No** — unsigned, blocked with error 577 |

**For development**, you have two options:
1. **Enable test-signing** on your dev machine (see below) to use the source-built driver
2. **Download the signed release** from pawnio.eu and place it at `tools/PawnIO/dist/PawnIO.sys`

**For production/distribution**, always use the officially signed PawnIO.sys from pawnio.eu.

### Enabling test-signing mode (development only)

Test-signing allows Windows to load unsigned kernel drivers. This is a boot-time setting that affects your entire system.

**Enable:**
```powershell
# Requires admin (elevated PowerShell)
bcdedit /set testsigning on
# Reboot required
shutdown /r /t 0
```

**Disable:**
```powershell
bcdedit /set testsigning off
shutdown /r /t 0
```

**What to expect:**
- A "Test Mode" watermark appears in the bottom-right corner of the desktop
- All unsigned/test-signed kernel drivers can load (not just PawnIO)
- Secure Boot must allow it — most consumer/gaming PCs do; some enterprise UEFI configs may block it
- No special certificates or tools are needed

**Requirements:**
- Windows 10/11 (any edition)
- Admin privileges to run `bcdedit`
- Secure Boot not locked to reject test-signing (rare on consumer hardware)
- A reboot after each toggle

### Cleaning up a broken PawnIO service

If you previously ran lhm-server with an unsigned PawnIO.sys (without test-signing), a broken service entry may exist. The retry logic in lhm-server will auto-clean this, but you can also clean it up manually:

```powershell
# Requires admin
sc delete PawnIO
del C:\Windows\System32\drivers\PawnIO.sys
```

### Build workflow

```
tools/PawnIO_Latest_Check/update_pawnio.ps1  # Download signed PawnIO.sys from GitHub releases
tools/PawnIO/build.ps1                       # OR build PawnIO.sys from source (WDK + CMake required)
tools/lhm-server/build.ps1                   # Build lhm-server.exe (embeds PawnIO.sys if present)
python build.py                              # Full pipeline: PawnIO -> lhm-server -> lil_bro.exe
```

**Recommended:** Run `update_pawnio.ps1` to fetch the latest signed PawnIO.sys from GitHub. It checks for new releases, verifies SHA256, and extracts the x64 signed driver to `tools/PawnIO/dist/PawnIO.sys`.

The lhm-server build auto-triggers `tools/PawnIO/build.ps1` (source build) if `tools/PawnIO/dist/PawnIO.sys` is missing. If you prefer the signed binary, run `update_pawnio.ps1` first.

---

## Writing new checks

1. Create `src/agent_tools/your_check.py`
2. Implement a pure `analyze_your_check(specs: dict) -> dict` function (no system calls, reads from specs)
3. Return a dict with at minimum `check`, `status`, `message`, `can_auto_fix` keys
4. Wire it into `phase_config.py` — add your check function to the run phase method
5. Add a handler function and registry entry to `src/pipeline/fix_dispatch.py` using `@register_fix("your_check")` decorator if `can_auto_fix: True`
6. Add a fallback template to `FALLBACK_PROPOSALS` in `action_proposer.py` for offline/LLM-fallback scenarios
7. Write mocked tests in `tests/test_your_check.py`

The Phase protocol (in `base.py`) ensures your check's findings flow cleanly through the orchestrator: Phase 4 (Config) → Fix dispatch → Approval UX → Phase 5 (Verification).

---

## Key rules

- **Safety first** — every system modification goes through `prompt_approval()` before executing.
- **No silent changes** — a System Restore Point is created before any fixes are applied.
- **Always use `uv`** — never `pip install` directly.
- **GUI via PySide6** — GUI is the default; `--terminal` flag preserves the CLI path. New UI work uses PySide6 (not PyQt).
- **Offline** — no telemetry, no external APIs beyond driver version checks and the one-time GGUF model download.

---

# Architecture

## File Tree

```
src/
  main.py                — Thin entry point; GUI by default, --terminal for CLI
  console_attach.py      — Win32 console attach helper for --terminal mode
  bootstrapper.py        — UAC escalation + Restore Point creation
  _version.py            — Single source of truth for version string
  gui/                   — PySide6 desktop application
    app.py               — Application setup + app lifecycle
    pipeline_controller.py — Wires PipelineWorker signals to UI panels
    startup_coordinator.py — Manages splash → main window transition; owns dashboard fix threads
    bridge.py            — Qt signal bridge between pipeline and GUI
    signals.py           — Shared signal definitions
    settings.py          — QSettings persistence (window geometry, preferences)
    startup.py           — Startup orchestrator worker (theme → settings → bridge → LLM → spec dump)
    worker.py            — PipelineWorker, _MonitorFixWorker, _MonitorRefreshWorker
    theme/               — QSS theme package
      __init__.py        — Public re-exports
      tokens.py          — Design token constants (colors, fonts, spacing)
      helpers.py         — QSS generation helpers
      stylesheet.py      — Main window stylesheet
      stylesheet_dialogs.py — Dialog-specific QSS
      stylesheet_foundation.py — Base/reset QSS
      stylesheet_interactive.py — Button/input QSS
      stylesheet_monitoring.py  — Dashboard monitoring card QSS
    widgets/             — Reusable UI widgets
      ai_setup_dialog.py     — AI model download dialog
      approval_dialog.py     — Fix approval dialog
      batch_selection_dialog.py — Batch fix selection
      benchmark_row.py       — Benchmark result row
      confirm_dialog.py      — Generic confirmation dialog
      dashboard.py           — Dashboard with live stat tiles
      monitor_refresh_card.py — Monitor refresh rate card + Fix Now button
      mouse_poll_card.py     — Mouse polling card + Fix Now button
      mouse_ready_dialog.py  — Mouse polling readiness prompt
      output_panel.py        — ANSI-aware output panel
      output_view.py         — Output view container
      splash.py              — Animated splash screen
      stat_card.py           — Reusable stat/metric card
      status_bar_widget.py   — Status bar with phase state
      thermal_chart.py       — Live thermal chart widget
    windows/             — Top-level windows
      main_window.py     — MainWindow (dashboard + pipeline tabs)
  pipeline/
    __init__.py          — Package marker
    _state.py            — Shared _llm state (get_llm/set_llm)
    base.py              — PipelineContext + Phase protocol for modular phases
    approval.py          — Proposal display, selection parsing, fix execution, manifest session start
    fix_dispatch.py      — Check->fix dispatch registry (with revert manifest integration)
    phase_revert.py      — Phase 6: Interactive revert flow (menu option 4 or --revert)
    thermal_gate.py      — Pre-benchmark thermal safety check
    phase_bootstrap.py   — Phase 1: Bootstrapping & Safety (UAC, restore point)
    phase_scan.py        — Phase 2: Deep System Scan (always re-dumps live specs; startup snapshot is degraded-mode fallback)
    phase_baseline.py    — Phase 3: Baseline Benchmark (Cinebench single-core, thermals)
    phase_config.py      — Phase 4: Optimization Configuration Check (all checks, LLM proposals, batch approval)
    phase_final.py       — Phase 5: Final Verification Benchmark (skips when fixes_applied == 0)
    phases.py            — 5-phase optimization orchestrator + PipelineContext management
    post_run_cleanup.py  — Deletes ./lil_bro/ on exit; preserves CWD-root persistent logs
  collectors/
    spec_dumper.py       — Aggregates all system data into unified JSON
    sub/                 — Individual collectors (WMI, dxdiag, nvidia-smi, EDID, monitor, NVIDIA Profile)
      lhm_sidecar.py     — LibreHardwareMonitor process lifecycle management
      lhm_http.py        — HTTP polling against LHM localhost:8085 (capped at 10 MB)
      lhm_discovery.py   — LHM install + binary discovery
      lhm_process_utils.py — LHM process start/stop/readiness helpers
      nvidia_profile_dumper.py — NVIDIA Profile collector (uses utils/nvidia_npi.py for shared export + setting-ID surface)
  agent_tools/           — Modular system checks (one file per check)
    display.py           — Monitor refresh rate analysis
    display_setter.py    — Applies refresh rate changes via Win32 ChangeDisplaySettingsEx
    game_mode.py         — Windows Game Mode registry
    power_plan.py        — Power plan detection + switching
    xmp_check.py         — RAM XMP/EXPO detection
    rebar.py             — Resizable BAR detection
    temp_audit.py        — Temp folder bloat + cleanup
    mouse.py             — Mouse polling rate
    quick_status.py      — Fast registry/QSettings reads for dashboard tile init
    nvidia_profile.py    — NVIDIA Profile Inspector setting detection + analysis
    nvidia_profile_setter.py — Apply NVIDIA Profile Inspector setting changes
    thermal_guidance.py  — Thermal analysis + pre-benchmark idle safety gate
  llm/                   — LLM integration (optional — tool works without it)
    model_loader.py      — GGUF model loading + first-run download from HuggingFace
    action_proposer.py   — Findings → LLM JSON proposals; FALLBACK_PROPOSALS + propose_for_check() for offline/dashboard use
  benchmarks/
    cinebench.py         — BenchmarkRunner orchestration
    cinebench_discovery.py — Cinebench install auto-detect (12 paths)
    cinebench_parser.py  — Cinebench result file parsing
    cinebench_monitor.py — Background thermal polling during Cinebench runs
    thermal_monitor.py   — Background LHM temperature polling during benchmarks
  utils/
    action_logger.py     — System-modification audit log → ./lil_bro_actions.log (CWD root, survives cleanup). Outcome-tagged entries ([PASS]/[FAIL]/[APPROVED]/[SKIPPED]); logs system changes only.
    debug_logger.py      — Process debug log → ./lil_bro_debug.log; always-on in GUI mode (INFO level minimum, DEBUG with --debug); sys.excepthook + threading.excepthook installed at GUI startup.
    dump_parser.py       — Extracts slim hardware summary from full_specs.json for LLM
    errors.py            — Typed exception hierarchy: LilBroError, AdminRequiredError, ScannerError, RestorePointError, SetterError, NvapiInitError (subclass of SetterError, signals AMD-only-system case)
    nvidia_npi.py        — Single source of truth for NVIDIA Profile Inspector helpers: SETTING_IDS, TARGET_VALUES, DLSS_LETTER_MAP, DLSS_PRESETS, find_npi_exe, calculate_fps_cap, export_current_profile
    nip_io.py            — .nip XML parsing (parse_nip, parse_nip_with_retry) + Windows file-handle readiness wait (wait_for_nip_ready)
    formatting.py        — Colorama terminal UI helpers (print_step, print_success, etc.); set_output_sink routes to GUI when installed
    _console.py          — Internal console formatting helpers (extracted from formatting.py)
    integrity.py         — SHA-256 exe hash verification (frozen builds only)
    paths.py             — Centralized CWD-relative path helper (lil_bro/ runtime dir, persistent log paths)
    platform.py          — Platform detection (IS_WINDOWS) + admin privilege check (is_admin)
    progress_bar.py      — AnimatedProgressBar: plasma-sweep terminal animation; set_progress_sink routes to GUI when installed
    revert.py            — Session manifest I/O (start/append/load, JSON schema v1, per-session archiving, atomic write via tmp+os.replace); per-fix revert handlers; System Restore fallback launcher
    display_utils.py     — Win32 DEVMODE struct + display mode enumeration via ctypes
    subprocess_utils.py  — Centralized subprocess runner with timeout and error handling
    pawnio_check.py      — PawnIO kernel driver installation detection (registry check)
build.py               — Automated build pipeline (5 steps: PawnIO update → lhm-server → PyInstaller → integrity manifest)
lil_bro.spec           — PyInstaller onefile build specification (hiddenimports covers all src/gui/widgets/*)
install_deps.ps1       — One-command dev setup (Python, uv, .NET 8, WDK, submodules)
tools/
  PawnIO/              — PawnIO kernel driver source + WDK build script (fallback path)
  PawnIO_Latest_Check/ — Primary PawnIO.sys source: fetches latest signed binary from namazso/PawnIO.Setup GitHub releases; WDK build is fallback if offline/unavailable
  lhm-server/          — Custom C# thermal sensor server (LibreHardwareMonitor + PawnIO)
  nvidiaProfileInspector/ — Bundled NVIDIA Profile Inspector tool (C# WPF app for GPU setting management)
tests/                 — Unit tests, all mocked (no real system modifications)
docs/                  — All progress docs, plans, reports, and notes go here
memory-bank/           — Project design docs (brief, progress, patterns, active context)
```

## Pipeline Architecture

Implemented as modular Phase classes inheriting context via PipelineContext dataclass. Phases 1–5 run automatically during optimization; Phase 6 is a standalone user-triggered revert workflow.

1. **Bootstrap Phase** (`phase_bootstrap.py`) — UAC check, System Restore Point creation
2. **Scan Phase** (`phase_scan.py`) — Always re-dumps live system specs (startup snapshot is a degraded-mode fallback only); WMI, dxdiag, nvidia-smi, NVIDIA Profile Inspector, EDID, monitor enum → unified JSON. Running the pipeline twice in one session now finds nothing the second time (rescan idempotency).
3. **Baseline Bench Phase** (`phase_baseline.py`) — Cinebench 2026 single-core + thermal baseline
4. **Config Phase** (`phase_config.py`) — All agent_tools checks (display, power, RAM, GPU, thermal, NVIDIA Profile) → LLM proposals (or static fallback) → numbered batch approval UX
5. **Final Phase** (`phase_final.py`) — Re-run benchmark, compare delta vs baseline. Skips with a distinct "no changes applied" message when `fixes_applied == 0`.
6. **Revert Phase** (`phase_revert.py`) — User-triggered via menu option 4 or `--revert`; loads session manifest (`revert.py`), dispatches per-fix revert handlers in reverse order (display → NVIDIA profile → game mode → power plan); falls back to Windows System Restore (`rstrui.exe`) on partial failure. **No additional restore point is created before reverting** — doing so would create a second "lil_bro" restore point and leave the user unable to tell which one to select in `rstrui.exe`. The single restore point created at bootstrap (Phase 1) is the one to use if System Restore is needed. The session manifest accumulates across multiple pipeline runs in the same session — one Revert undoes all runs' changes in newest-first order.

All phases share state via `PipelineContext` (LHM sidecar, thermal monitor, specs, LLM, benchmark results).

## GUI Architecture

The default mode launches a PySide6 desktop app. The startup sequence is:

1. `SplashDialog` shown immediately; five async steps load in a `StartupOrchestrator` worker thread (theme → settings → bridge → LLM → spec dump).
2. `StartupCoordinator` receives the pre-loaded specs and transitions to `MainWindow` after the splash completes.
3. `MainWindow` hosts a Dashboard tab (live stat tiles) and a Pipeline tab (phase-card progress + output panel).
4. Dashboard "Fix Now" buttons route through `_MonitorFixWorker` / `_MonitorRefreshWorker` — both are guarded against concurrent pipeline runs and double-clicks. Fixes are recorded in the shared session manifest and are revertible.
5. `PipelineController` runs the 5-phase optimization pipeline on a `PipelineWorker` thread and feeds signals to the output panel and phase cards.

CLI mode (`--terminal`) bypasses all GUI code and runs the original console pipeline unchanged.

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

---

## See Also

- **[README.md](README.md)** — End-user guide and feature overview
- **[CONTRIBUTING.md](CONTRIBUTING.md)** — How to report bugs and submit pull requests
- **[CLAUDE.md](CLAUDE.md)** — Full technical reference for AI assistants
