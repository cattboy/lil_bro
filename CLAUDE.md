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
  - **docs/NPI_CustomSettingNames.xml** is the canonical reference for all NVIDIA Profile Inspector setting IDs. Cross-reference any SETTING_IDS changes in nvidia_profile_dumper.py against this file's HexSettingID values.

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

## Serena MCP Tools

Serena is started manually by the user before each session. **When Serena is available, always prefer its tools over built-in Claude Code tools for all code work.** Do not reach for Grep, Glob, or Read to navigate code when a Serena tool covers the same task.

| Task | Use Serena | NOT built-in |
|------|-----------|-------------|
| Find a function / class / symbol | `mcp__serena__find_symbol` | Grep |
| Search code by pattern | `mcp__serena__search_for_pattern` | Grep |
| Get file/module overview | `mcp__serena__get_symbols_overview` | Read |
| Browse project structure | `mcp__serena__list_dir` | Glob |
| Locate a file | `mcp__serena__find_file` | Glob |
| Edit a symbol body | `mcp__serena__replace_symbol_body` | Edit |
| Cross-file refactoring | Serena symbol tools | Grep + Edit |
| Find all callers of a symbol | `mcp__serena__find_referencing_symbols` | Grep |
| Rename a symbol project-wide | `mcp__serena__rename_symbol` | sed / Edit |
| Persist project knowledge | `mcp__serena__write_memory` / `read_memory` | Memory files |

**Only use built-in tools when:**
- Reading non-code files (markdown, config, logs, XML)
- Serena is not running (fall back to Grep/Glob/Read, note the limitation)
- The target file is outside the project root

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full file tree, 5-phase pipeline, and tech stack.

Key entry points: `src/main.py` → `src/pipeline/phases.py` → phase files → `src/agent_tools/` checks.

---

## Design System
Always read `DESIGN.md` before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

---

## Development Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md). Current test count: 387.

---

## gstack Skills Location

gstack skill binaries live at `.claude/skills/gstack/bin/` (project-local), **not** `~/.claude/skills/gstack/bin/`. Always use the project-local path when invoking gstack binaries directly (e.g., `.claude/skills/gstack/bin/gstack-config`).

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
