# Contributing to lil_bro

This is a solo project in active development. This file covers everything you need to run, test, and build it locally.

---

## Requirements

- **Python 3.11+** (3.13 tested)
- **uv** — fast Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **Windows 10/11** — this tool is Windows-only (uses WMI, winreg, ctypes Win32 APIs)

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

Current suite: **188 tests**, all passing.

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
1. Runs `PyInstaller lil_bro.spec --noconfirm`
2. Generates `dist/integrity.json` with the SHA-256 hash of the exe
3. Prints the output size and path

The `.spec` file (`lil_bro.spec`) is the PyInstaller build configuration — edit it if you need to add data files or hidden imports.

**Note:** `llama-cpp-python` has not been fully validated under PyInstaller bundling yet. Test on target hardware before distributing a build with LLM support.

---

## Project structure

```
src/
  main.py           — Pipeline orchestrator (5 phases) + menu
  agent_tools/      — One file per system check (game_mode, display, power_plan, ...)
  collectors/       — Hardware data collection (WMI, dxdiag, nvidia-smi, EDID, ...)
  llm/              — Optional LLM integration (model loader + action proposer)
  benchmarks/       — Cinebench runner + thermal monitor
  utils/            — Shared helpers (formatting, logging, paths, progress bar, ...)
tests/              — Unit tests (all mocked)
docs/               — Design notes, plans, vendor reference docs
build.py            — .exe build script
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

## Writing new checks

1. Create `src/agent_tools/your_check.py`
2. Implement a pure `analyze_your_check(specs: dict) -> dict` function (no system calls, reads from specs)
3. Return a dict with at minimum `check`, `status`, `message`, `can_auto_fix` keys
4. Wire it into `_run_pipeline()` in `main.py`
5. Add an auto-fix case to `_execute_fix()` if `can_auto_fix: True`
6. Add a fallback template to `_FALLBACK` in `action_proposer.py`
7. Write mocked tests in `tests/test_your_check.py`
