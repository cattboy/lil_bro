---
name: refactor-orchestrator
description: |
  Multi-stage refactor pipeline for large Python files. Scans src/ for files
  over a threshold (default 300 lines), spawns a 3-agent investigation team
  per target (architecture usage, internal symbols, test coverage), drafts a
  decomposition plan, runs an opus devil's-advocate against the plan, then
  executes in worker+critic pairs with atomic commits per chunk.
  Use when asked to "refactor", "decompose", "split this file", "break up
  big files", or "find files to refactor". Proactively suggest when the user
  mentions a file feeling too big, when health/qa output flags file size, or
  after a feature lands and leaves a module bloated.
---

# Refactor Orchestrator

Multi-stage refactor pipeline. One trigger, six phases, fully auditable subagent transcripts. Designed for lil_bro's codebase — knows about Serena symbol tools, the human-in-the-loop approval contract, PyInstaller bundling, and the 90th-percentile line count of this project.

## When to use this skill
- User asks to "refactor", "decompose", "split this file", or "find files to refactor"
- A file has grown past ~300 lines and has multiple responsibilities
- After a feature lands and leaves a module bloated

Don't use it for tiny cleanups (renames, single-line changes) or cross-file refactors that move symbols *between* existing files — v1 only extracts new files from one bloated file.

## Architecture

```
Phase 1: Discovery        → script lists large files; user picks targets
Phase 2: Investigation    → 3 parallel agents per target (read-only)
Phase 3: Plan synthesis   → orchestrator drafts decomposition plan
Phase 4: Devil's advocate → opus tears the plan apart; revise; user approves
Phase 5: Implementation   → per-chunk: worker → simplifier critic → test → commit
Phase 6: Report           → before/after stats, commits, deferred follow-ups
```

Phases are **serial per target file** — finish file A through all phases before starting file B. Within Phase 2, the 3 investigation agents run **in parallel**.

## Conventions

- **`--dry-run`** flag: halt after Phase 3 (plan written, no implementation). User can review and re-run.
- **`--threshold N`** flag: override the default 300-line threshold for this invocation.
- **One critic round per chunk** in v1. Worker reads critic edits once and ships.
- **Atomic commits per chunk**, never bundled. Each commit must leave tests green.
- **Halt on test failure** — never auto-fix a failing test in Phase 5; ask the user.
- **End with a status line:** `DONE`, `DONE_WITH_CONCERNS`, or `BLOCKED`.

---

## Phase 1 — Discovery

Run the discovery script with the active threshold:

```bash
.venv/Scripts/python .claude/skills/refactor-orchestrator/scripts/find_large_files.py \
  --threshold 300 \
  --root src/
```

(Use `.venv/Scripts/python` per CLAUDE.md — the venv must be active for any Python invocation in this repo.)

It returns JSON: a list of `{path, lines, first_docstring_line}` sorted descending. Pretty-print the top 20 as a numbered table:

```
#   Lines  Path                                          Summary
1   794    src/gui/theme/stylesheet.py                   PySide6 QSS stylesheet ...
2   490    src/benchmarks/cinebench.py                   BenchmarkRunner: Cinebench ...
3   420    src/collectors/sub/lhm_sidecar.py             LibreHardwareMonitor process ...
...
```

Then ask the user which to target:

```
AskUserQuestion:
  question: "Which file(s) should we refactor in this run?"
  header: "Targets"
  multiSelect: false
  options:
    - {label: "Top 1 (recommended)",       description: "Process just the largest file"}
    - {label: "Top 3",                     description: "Process files #1, #2, #3 in serial order"}
    - {label: "Files >500 lines only",     description: "Process only files crossing the higher bar"}
```

The "Other" option (auto-provided by AskUserQuestion) lets the user free-form a list like "1, 5, 9" or specific paths.

**No subagents fire until the user signs off** — the per-file fanout is expensive. Echo back the final target list and proceed.

---

## Phase 2 — Investigation (parallel, per target file)

For each target file, in serial order across files:

### Derive the module path

`src/foo/bar/baz.py` → conceptually `src.foo.bar.baz`. Check `tests/conftest.py` or a known-good import elsewhere to confirm whether the import root is `src.X.Y` or `X.Y` in this repo.

### Spawn 3 subagents in one message (true parallel)

For each agent, read its instructions file once, append a task block, and pass the combined text as the `prompt` argument:

```
agent_text = Read(".claude/skills/refactor-orchestrator/agents/architecture-mapper.md")

prompt = agent_text + f"""

---

## Target

File: {target_file}
Module path: {derived_module_path}

Execute now and return the report as Markdown.
"""
```

The 3 spawns, in the same message:

| Agent              | subagent_type | Instructions file                          |
|--------------------|---------------|--------------------------------------------|
| architecture-mapper| `Explore`     | `agents/architecture-mapper.md`            |
| symbol-mapper      | `Explore`     | `agents/symbol-mapper.md`                  |
| test-coverage-mapper| `Explore`    | `agents/test-coverage-mapper.md`           |

All three are `Explore` — read-only by construction (no `Edit`/`Write`). They inherit the parent model; sonnet is fine, haiku is acceptable if context is tight.

### Collect results

Receive the 3 Markdown reports. Hold them in your own context — do not write them to disk. They're transient and will be summarized into the plan file in Phase 3.

---

## Phase 3 — Plan synthesis

Read `references/decomposition-patterns.md` to ground yourself in the available refactor shapes. Then draft the plan.

Ensure `docs/refactor-plans/` exists (create with `mkdir -p` if not). Write to: `docs/refactor-plans/{target_basename_without_ext}-plan.md`.

### Plan template

```markdown
# Refactor plan: {target_file}

## Current shape
- Line count: {N}
- Top-level symbols: {count}
- Top 3 coupling concerns from architecture-mapper:
  1. ...
  2. ...
  3. ...

## Target shape
Proposed new module(s):
- `{new_module_path}` — {purpose}. Symbols moved in: {list}
- `{new_module_path_2}` — ...

Target file after refactor: ~{estimated_remaining_lines} lines (down from {N})

Pattern(s) applied (from references/decomposition-patterns.md):
- {e.g. "Pattern 6: Separate Configuration from Behavior — for the QSS string blocks"}

## Chunks
Each chunk is one atomic commit. Tests must pass between chunks.
Chunks should each be ≤200 LOC of movement; split larger ones in two.

### Chunk 1: {short description}
- **Symbols moved:** {list}
- **New files created:** {list}
- **Imports updated:** {list of files where `from X import Y` lines change}
- **Tests that should pass after:** `pytest -k {basename}`
- **Serena hygiene:** {Pattern A symbol-only | Pattern B mixed | Pattern C wholesale | Pattern D new file — see references/serena-safety.md}

### Chunk 2: ...

## Untested risk
From test-coverage-mapper: symbols with zero test coverage that this plan moves:
- {symbol}: {target_module}

## Devil's advocate concerns (filled in by Phase 4)
- {category}: {concern} — **resolution:** {how the plan was changed}

## Status
- [ ] Phase 4 devil's advocate complete
- [ ] User approved
- [ ] Implementation complete
- [ ] All tests passing
```

---

## Phase 4 — Devil's advocate

Spawn one subagent (general-purpose, opus model):

```
Agent(
  subagent_type="general-purpose",
  model="opus",
  description="Devil's advocate: critique refactor plan for {basename}",
  prompt=<contents of agents/devils-advocate.md> + f"""

---

## Inputs

**Plan file:** docs/refactor-plans/{basename}-plan.md (READ THIS FIRST)

**Target file:** {target_file}

**Architecture-mapper report:**
{architecture_report_full_text}

**Symbol-mapper report:**
{symbol_report_full_text}

**Test-coverage-mapper report:**
{coverage_report_full_text}

Execute your critique now.
"""
)
```

Receive the critique. Two outcomes:

- **No blocking concerns:** proceed directly to Phase 4.5
- **Blocking concerns present:** revise the plan in place to address each one. Append a "Devil's advocate concerns" entry per concern with the resolution applied.

If you revised, spawn the devil's advocate **once more** with the updated plan (cap at 2 rounds total). If round 2 still finds blocking concerns the plan can't address, halt and ask the user — they may want a different decomposition strategy.

### Phase 4.5 — User approval

After the devil's advocate is satisfied (or you've hit the round cap and want to proceed anyway), surface the final plan file path and ask:

```
AskUserQuestion:
  question: "Approve the refactor plan and start implementation?"
  header: "Plan approval"
  multiSelect: false
  options:
    - {label: "Approve — start implementation",   description: "Run all chunks in plan order with worker+critic pairs"}
    - {label: "Need adjustments",                  description: "Tell me what to change in the plan"}
    - {label: "Abort — leave the plan file",       description: "Stop here; the plan stays on disk for later"}
```

If the user picks abort, end the run with `BLOCKED` and surface the plan file path.

If `--dry-run` was set, end here regardless with `DONE_WITH_CONCERNS` and the plan path.

---

## Phase 5 — Implementation (worker + simplifier pairs, per chunk)

Read `references/serena-safety.md` once before the first chunk — it tells you when to call `mcp__serena__restart_language_server` and which chunk patterns mix Serena with built-in edits safely.

Load Serena schemas you'll need:

```
ToolSearch: select:mcp__serena__find_symbol,mcp__serena__get_symbols_overview,mcp__serena__replace_symbol_body,mcp__serena__insert_after_symbol,mcp__serena__insert_before_symbol,mcp__serena__restart_language_server
```

For each chunk in plan order:

### Step 1: Worker pass
Execute the chunk inline using the CLAUDE.md decision gate:
- **Symbol body edits** → Serena `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`
- **Module-level lines** (imports, constants, `__all__`, docstring) → built-in `Edit`
- **New file creation** → built-in `Write`
- **Wholesale rewrite of an existing file** → `Read`, compose, `Write` (Pattern C in serena-safety.md)

Per Pattern B in serena-safety.md, run all Serena symbol edits first, then any built-in `Edit`s on the same file.

### Step 2: Simplifier critic pass
Get the changed files for this chunk:

```bash
git diff --name-only HEAD
```

Spawn the simplifier as the chunk critic:

```
Agent(
  subagent_type="code-simplifier:code-simplifier",
  description="Simplify chunk {N} diff",
  prompt=f"""
Scope: only the uncommitted diff against HEAD. Files touched: {file_list}.

Refine for:
- Accidental complexity (extra layers, premature abstraction)
- Inconsistencies with surrounding code style
- Anything that improves clarity without changing behavior

Edit directly. Do not commit — the orchestrator will commit after running tests.
If the diff is already clean, say so explicitly with one sentence on what you checked.
"""
)
```

The simplifier edits inline. No second pass — one round per chunk in v1.

### Step 3: Serena LS hygiene
Run the end-of-chunk checklist from `references/serena-safety.md`:

- Did this chunk include any non-Serena edit to a `.py` file? → `mcp__serena__restart_language_server`
- Did this chunk create a new `.py` file? → `restart_language_server`
- Otherwise → skip restart

(The simplifier subagent likely used built-in `Edit`/`Write` since that's its default — assume restart is needed unless certain.)

### Step 4: Test gate
Run targeted tests:

```bash
.venv/Scripts/python -m pytest tests/ -k {target_basename_no_ext} -x --tb=short
```

- **Green:** continue to commit
- **Red:** halt. Ask the user:

```
AskUserQuestion:
  question: "Chunk {N} broke tests. What now?"
  header: "Test failure"
  multiSelect: false
  options:
    - {label: "Roll back this chunk",      description: "git reset --hard HEAD; skip to next chunk"}
    - {label: "Let me fix it manually",    description: "Halt here; I'll fix and you continue"}
    - {label: "Abort the whole run",       description: "Stop; surface progress so far"}
```

### Step 5: Atomic commit
```bash
git add -A
git commit -m "refactor({module_name}): {chunk description}

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

(The trailer is required per CLAUDE.md global rules. Use the model name actually running this session; the example above is the default.)

Update the plan file's status checkboxes for this chunk. Capture the commit hash for the Phase 6 report.

Move to the next chunk.

---

## Phase 6 — Completion & report

After the last chunk lands:

### Step 1: Full test suite

```bash
.venv/Scripts/python -m pytest tests/ -x --tb=short
```

If this fails despite all chunks passing the targeted tests, surface the failure — something downstream depends on the target file in a way the investigation missed. Don't commit a fix; surface and halt.

### Step 2: Confirm the target shrunk

Re-run the discovery script. Verify the target file is now under threshold (or at least substantially smaller than before — sometimes a large file resists reduction past a floor of necessary boilerplate).

### Step 3: Write the report

Path: `docs/refactor-plans/{target_basename_no_ext}-report.md`

```markdown
# Refactor report: {target_file}

## Outcome
- Before: {N_before} lines
- After (target file): {N_after} lines
- New modules: {list of paths with line counts}
- Net code change: {delta} lines across {K} files

## Chunks completed
| # | Description                  | Commit hash | LOC moved |
|---|------------------------------|-------------|-----------|
| 1 | Extract QSS card styles      | abc1234     | 180       |
| 2 | ...                          | def5678     | 120       |

## Test suite
- Before: {X} tests passing
- After: {Y} tests passing
- New tests added: 0 (refactor-only)

## Devil's advocate concerns addressed
- {category}: {concern} → {resolution}

## Deferred follow-ups
- {anything the plan, critic, or test gate flagged but didn't address}

## PyInstaller note (if applicable)
If new modules landed under `src/gui/widgets/`, they need adding to `lil_bro.spec`
`hiddenimports` per CLAUDE.md. Files to add:
- {list, or "None — no new modules under src/gui/widgets/"}
```

### Step 4: Surface to user

End the run with a status line and the report path:

```
DONE — refactor of {target_file} complete.
  Before: {N_before} lines → After: {N_after} lines
  {K} chunks, {K} commits
  Full test suite green
Report: docs/refactor-plans/{basename}-report.md
```

If there were deferred follow-ups, swap `DONE` for `DONE_WITH_CONCERNS` and lead with the most important one.

If the run halted partway, swap for `BLOCKED` and surface what's done, what's left, and the reason.

---

## Status codes

| Code                  | Meaning                                                                |
|-----------------------|------------------------------------------------------------------------|
| `DONE`                | Full pipeline completed cleanly                                        |
| `DONE_WITH_CONCERNS`  | Completed but with non-blocking issues (deferred follow-ups, etc.)     |
| `BLOCKED`             | Halted before completion; user action required to proceed              |

---

## What's out of scope for v1

- Non-Python files (no JS/TS/QSS support beyond the QSS-in-Python case)
- Cross-file refactors (moving symbols *between* existing files; v1 only extracts new files from one bloated file)
- Auto-PR creation (commits land on the current branch; user runs `/ship` after)
- `--aggressive-critique` mode (multiple critic rounds per chunk)
- Eval test cases via the skill-creator workflow (deferred until skill is stable from real runs)
