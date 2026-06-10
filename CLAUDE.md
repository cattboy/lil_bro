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
  - **docs/NPI_CustomSettingNames.xml** is the canonical reference for all NVIDIA Profile Inspector setting IDs. Cross-reference any SETTING_IDS changes in `src/utils/nvidia_npi.py` against this file's HexSettingID values.

### Safety & User Trust
- Every system modification must call `prompt_approval()` before executing — no silent changes, ever.
- System Restore Point must be created via `bootstrapper.py` before any modifications begin.
- **Do NOT create a restore point before the revert phase.** A second restore point at revert time creates two identically-labelled "lil_bro" entries in `rstrui.exe`, leaving the user unable to tell which one predates the fixes. The Phase 1 restore point is the correct target if System Restore is ever needed.
- No external HTTP calls, telemetry, or cloud APIs beyond driver version verification URLs and the one-time model download from HuggingFace.

### Code Architecture
- New system checks belong in `src/agent_tools/` as independent modules.
- Each check function returns a structured dict with at minimum `status` and `message` keys.
- Always implement multi-method fallbacks — never hard-fail when a tool (nvidia-smi, dxdiag, etc.) is missing. Fall back to WMI or registry alternatives.
- GUI via PySide6 (default). CLI mode preserved via `--terminal`. New visual work uses PySide6; do not introduce PyQt.

### Dialogs
- All dialogs MUST be built from `CardDialog` in `src/gui/widgets/dialogs.py` — never a raw `QMessageBox` or a hand-rolled `QDialog`. The template owns the DESIGN.md card styling (surface card, tone-coloured icon, JetBrains-Mono title, accent-glow primary button, WASD `(W)`/`(S)` buttons, Esc handling) via the object-name-driven `_qss_card_dialog`.
- `tone="accent|warning|error|info|success"` drives the icon tint via the `cardTone` property — distinct from the `sev=low|medium|high` severity property and from `statTone`; do not conflate them. Pass `secondary_label` only for a two-button confirm (Esc rejects); omit it for a single-button acknowledgement (Esc accepts). Secondary buttons auto-get `setAutoDefault(False)` (the WASD popout rule).
- `icon` is caller-supplied and defaults to deriving a glyph from `tone`; pass `icon=None` for no icon (e.g. the `accent_bar=True` variant). The default glyphs are an interim stand-in — `tokens.py` blacklists emoji as design elements, so a QIcon migration is tracked in TODOS (T-027); do not enshrine specific glyphs as a design rule.
- Specialized dialogs (`BatchSelectionDialog`, `AISetupDialog`, `SplashDialog`) are the only exemptions. Every new `src/gui/widgets/` module still needs a `lil_bro.spec` hiddenimports entry.

### Dashboard Fix Pattern
When a fix can be triggered from a Dashboard card button (outside the pipeline `ApplyPhase`), follow this pattern — see `_MonitorFixWorker` in `src/gui/worker.py` as the reference implementation:

1. **Always route through `execute_fix(check_name, specs)`** (`src/pipeline/fix_dispatch.py`) — never call `_fix_*` handlers directly.
2. **Call `start_session_manifest(restore_point_created=False)` before `execute_fix()`** in the worker's `run()` method. It is a no-op if the pipeline already ran — safe to call unconditionally. Without it, `_record_revertible()` inside the handler writes into an uninitialized manifest and the fix is silently non-revertible.
3. **The check name passed to `execute_fix` must exactly match the `@register_fix` key** in `fix_dispatch.py` — same string the analyzer returns in `"check"`.
4. **Pass a filtered `specs` dict** narrowed to only the targeted item so the handler doesn't act on everything.
5. Wire the button signal → `StartupCoordinator` method → `QThread` + worker, mirroring `on_monitor_fix_requested` in `src/gui/startup_coordinator.py`.

### Mock GUI (dashboard card preview)
- `scripts/mock_gui.py` is the dev-only layout viewer: the real `MainWindow` + Dashboard fed entirely by `scripts/mock_fixtures.py`, with a floating state-switcher panel. It is NOT bundled — no `lil_bro.spec` entry, no production imports of it.
- **Every new dashboard card MUST also be wired into the mock GUI**: add per-state fixture data to `scripts/mock_fixtures.py` (reuse production constants so fixtures can't drift), a combo + `apply_*` method in `scripts/mock_gui.py` (`MockDriver`/`MockControls`) routing through the card's real public population API, and an entry in each `SCENARIOS` preset.
- Verify with `python scripts/mock_gui.py --smoke` (offscreen auto-cycle of all scenarios + multi-monitor) and extend `_smoke_report` with the new card's visibility/state.

### Subprocess & Temp Files
- **All subprocess temp files must be stored in CWD, not `%TEMP%`.** Use `get_temp_dir()` from `src/utils/paths.py` as the `dir=` argument for `tempfile.TemporaryDirectory()` and `tempfile.mkstemp()`. This ensures all runtime artifacts live under `./lil_bro/` and get cleaned up on exit via `post_run_cleanup.py`.
- Any new code spawning subprocesses that produce temp files must use `dir=str(get_temp_dir())` — never rely on the system default temp directory.
- PyInstaller's `runtime_tmpdir='.'` in `lil_bro.spec` ensures `_MEI*` extraction dirs are created in CWD. Stale `_MEI*` dirs from crashes are cleaned up by `_cleanup_stale_mei()` in `post_run_cleanup.py`.

### Bundling (PyInstaller)
- **Every new module under `src/gui/widgets/` MUST be added to `hiddenimports` in `lil_bro.spec`** (alphabetical with the existing widget list around line 81-91). PyInstaller's static analyzer can miss lazy imports inside method bodies, and the `try/except` in `app.py._on_finished` will swallow the resulting `ImportError` silently — the widget appears fine in dev mode but never renders in the bundled exe.
- After updating the spec, rebuild with `python -m PyInstaller lil_bro.spec --noconfirm`.

---

## Serena MCP Tools

Serena is started manually by the user before each session. A PreToolUse hook (`.claude/hooks/serena_guard.py`) **enforces** the split below: structural edits go through Serena's symbol tools; the built-in tools handle what Serena can't target. A blocked call always means "wrong tool — switch."

### Decision gate — before any tool call on a `.py` file

| What you're doing | Use | Hook |
|---|---|---|
| Edit a function / class / method body | `mcp__serena__replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`, `rename_symbol` | **blocks** built-in `Edit` |
| Edit a module-level line — import, constant, `__all__`, module docstring | built-in **`Edit`** | allows it (not a symbol) |
| Search code / find a symbol / find callers | `mcp__serena__search_for_pattern`, `find_symbol`, `find_referencing_symbols` | **blocks** `Grep`/`Glob` on `.py` |
| Module or symbol overview (exploring) | `mcp__serena__get_symbols_overview`, `find_symbol` | guidance only |
| Read exact text / whole-file context | built-in **`Read`** | allows it |
| Create a new `.py` file | built-in **`Write`** | allows it |
| Overwrite an existing `.py` wholesale | edit it instead | **blocks** `Write` on existing `.py` |
| Refactor via the shell (`sed -i`, redirects) | Serena symbol tools | **blocks** in-place `.py` shell edits |
| Resync Serena after a non-Serena `.py` edit (built-in `Edit`/`Write`/`rm`/shell) | `mcp__serena__restart_language_server` | guidance only |
| Persist project knowledge | `mcp__serena__write_memory` / `read_memory` | — |

**Rule of thumb:** is the target a *symbol* (function, class, method)? → Serena. Is it a *non-symbol line* (import, module constant) or plain-text / whole-file work? → built-in `Edit`/`Read`/`Write`. The hook draws the same line with `ast`, so it and this table never disagree.

### Editing — symbol vs. module level

- **Symbol body** (anything inside a `def`/`class`): `mcp__serena__replace_symbol_body`, or `insert_after_symbol` / `insert_before_symbol` to add adjacent code. The hook blocks the built-in `Edit` here.
- **Module level** (imports, module constants, `__all__`, the module docstring): built-in `Edit`. Serena's symbol tools target whole symbols, not individual lines, so non-symbol edits use `Edit`. The hook classifies the edit site with `ast` and lets `Edit` through.

### After a non-Serena edit — restart the language server

Serena's language server keeps an in-memory copy of each `.py` file, synced **only for Serena's own edits**. The split above guarantees non-Serena edits — every module-level line goes through the built-in `Edit`. Any built-in `Edit`/`Write`/`rm`, shell edit, or working-tree-changing `git` op (`checkout`, `rebase`, `reset --hard`) desyncs the LS; the next `replace_symbol_body` / `insert_*_symbol` then fails with `InvalidTextLocationError` or writes a stale body. A bare `git commit` does **not** desync — it leaves the working tree unchanged.

After any non-Serena change to a `.py` file, call `mcp__serena__restart_language_server` before the next Serena symbol read/edit. To restart rarely, batch per file: all Serena symbol edits first, then built-in module-level `Edit`s last. For a file being substantially rewritten, skip incremental Serena editing — `Read`, compose, `rm`+`Write`. Not hook-enforced; it's on you to call it.

### Reading code

Built-in `Read` on `.py` is allowed — and is required before any built-in `Edit` (the Edit tool refuses to run on an unread file, and the `claude-code` context excludes Serena's `read_file`). For *exploring* code, still prefer Serena: `get_symbols_overview` for a module's shape, `find_symbol` (with `include_body`) for one symbol, `search_for_pattern` for everything else. Don't `Read` a whole file just to locate one function.

### Creating new Python files

Use the built-in **Write** tool for new `.py` files — the `claude-code` context excludes `create_text_file` ("tools that would duplicate Claude Code's built-in capabilities"). The hook carves out `Write` on paths that do not yet exist and blocks it on existing `.py` files (a whole-file overwrite can't be scoped to a symbol).

### When NOT to use Serena

Serena's backend here (Pyright via SolidLSP) indexes **only Python**. For markdown, JSON, YAML, TOML, XML, `.txt`, config, logs, images — use built-ins directly. Same for any `.py` under `.claude/` (hooks, skills): Serena doesn't index that tree, and the hook carves it out.

### Schema loading
Serena tools are deferred — their schemas are not pre-loaded. Before calling any `mcp__serena__*` tool, load its schema first:
```
ToolSearch: select:mcp__serena__find_symbol   (or whichever tool you need)
```

---

## Architecture

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full file tree, 5-phase pipeline, and tech stack.

Key entry points (GUI): `src/main.py` → `src/gui/app.py` → `StartupCoordinator` → `PipelineController` → `src/pipeline/phases.py` → phase files → `src/agent_tools/` checks.
Key entry points (CLI): `src/main.py --terminal` → `src/pipeline/phases.py` → phase files → `src/agent_tools/` checks.

---

## Design System
Always read `DESIGN.md` before making any visual or UI decisions.
All font choices, colors, spacing, and aesthetic direction are defined there.
Do not deviate without explicit user approval.
In QA mode, flag any code that doesn't match DESIGN.md.

---

## Development Roadmap

See [`docs/ROADMAP.md`](docs/ROADMAP.md). Current test count: 785.

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

---

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
