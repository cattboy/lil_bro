# Contributing to lil_bro

This is a solo project in active development. This file covers everything you need to run, test, and build it locally.

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

Current suite: **312 tests**, all passing.

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

## Project structure

```
src/
  main.py           — Thin entry point (integrity, admin, banner, menu)
  pipeline/         — 5-phase pipeline orchestrator, split into 8 modules
    _state.py       — Shared LLM state (get_llm/set_llm)
    banner.py       — ASCII art banner
    menu.py         — 3-option menu loop + AI model setup
    approval.py     — Proposal display, selection parsing, fix execution
    fix_dispatch.py — Check→fix dispatch registry (FIX_REGISTRY dict)
    thermal_gate.py — Pre-benchmark thermal safety gate
    phases.py       — 5-phase pipeline orchestrator
  agent_tools/      — One file per system check (game_mode, display, power_plan, ...)
  collectors/       — Hardware data collection (WMI, dxdiag, nvidia-smi, EDID, ...)
  llm/              — Optional LLM integration (model loader + action proposer)
  benchmarks/       — Cinebench runner + thermal monitor
  utils/            — Shared helpers (formatting, logging, paths, progress bar, ...)
tests/              — Unit tests (all mocked)
docs/               — Design notes, plans, vendor reference docs
tools/
  PawnIO/           — PawnIO kernel driver source + WDK build script
  PawnIO_Latest_Check/ — Auto-updater: fetches signed PawnIO.sys from GitHub releases
  lhm-server/       — Custom C# thermal sensor server (LibreHardwareMonitorLib + PawnIO)
build.py            — .exe build pipeline (lhm-server + PyInstaller + integrity manifest)
install_deps.ps1    — One-command dev setup (Python, uv, .NET 8, WDK, submodules)
lil_bro.spec        — PyInstaller spec
pyproject.toml      — Single source of truth for all dependencies
```

See `CLAUDE.md` for the full architecture reference used by the AI assistant.

---

## Key rules

- **Safety first** — every system modification goes through `prompt_approval()` before executing.
- **No silent changes** — a System Restore Point is created before any fixes are applied.
- **Always use `uv`** — never `pip install` directly.
- **Terminal UI only** — no PyQt until explicitly requested.
- **Offline** — no telemetry, no external APIs beyond driver version checks and the one-time GGUF model download.

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
4. Wire it into `_run_pipeline()` in `src/pipeline/phases.py`
5. Add a handler function and registry entry to `src/pipeline/fix_dispatch.py` if `can_auto_fix: True`
6. Add a fallback template to `_FALLBACK` in `action_proposer.py`
7. Write mocked tests in `tests/test_your_check.py`
