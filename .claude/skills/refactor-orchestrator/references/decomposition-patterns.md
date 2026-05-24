# Decomposition Patterns

A reference for the plan-synthesis phase. The investigation reports tell you what's coupled to what; this file tells you the shape a refactor can take.

The orchestrator reads this once after Phase 2 (investigation) completes, before drafting the plan. The patterns below aren't a menu to pick one from — most real refactors blend two or three.

---

## Pattern 1: Extract Module

**When:** A cohesive cluster of symbols (functions or classes that share state, dependencies, or call each other tightly) is buried in a larger file. The hardest cluster to spot, because they often share *behavior* without being explicitly grouped.

**Shape:** Move the cluster to a new module. Either:
- Replace the original symbols with `from .new_module import ...` shims (lower-risk — preserves external imports)
- Update every external call site directly (cleaner — but more touchpoints)

**Gotchas:**
- The cluster may depend on module-level state in the original file. Lift that state with the cluster.
- If the cluster is imported by name from elsewhere (`from old_module import sym`), keeping the re-export shim is the lower-risk choice for the first refactor pass.

**lil_bro example:** `src/utils/formatting.py` has print helpers + colorama detection + ASCII/Unicode fallback. The colorama setup is a cluster of its own — could extract to `src/utils/_colorama_bootstrap.py` (leading underscore signals "internal").

---

## Pattern 2: Split IO from Logic

**When:** A module mixes pure computation with side effects (subprocess, filesystem, hardware, network). Side effects make the logic hard to test in isolation and the file hard to reason about.

**Shape:** New module pair — `{name}_io.py` touches the world, `{name}.py` does pure transformations on data. The IO module calls the logic module, never the reverse.

**Gotchas:**
- The "pure" half often needs new dataclasses to represent what the IO half used to pass around as side-effect ordering.
- Watch for hidden IO in the logic half — `print()` calls, `logger.info()`, exceptions raised with formatted strings that include filesystem paths.

**lil_bro example:** `src/collectors/sub/lhm_sidecar.py` (420 lines) mixes process lifecycle (`subprocess.Popen`, kill on exit) with HTTP polling (`requests.get`, JSON parsing) with sensor priority logic (pure dict transforms). Three-way split is natural: `lhm_process.py` + `lhm_http.py` + `lhm_sensors.py`.

---

## Pattern 3: Lift State into a Class

**When:** Module-level globals are read or written by many functions. Functions implicitly depend on each other through shared state, making the order of calls fragile.

**Shape:** Define a class that owns the state; convert the functions to methods. Existing call sites either instantiate the class or use a module-level singleton.

**Gotchas:**
- If the state is initialized at import time, you have to decide where init happens now. A lazy property on the class is usually safest.
- Singleton + tests = pain. Prefer dependency injection if the touch count is reasonable. Singletons are tempting because they preserve the call-site API exactly, but they hide test isolation problems.

**lil_bro example:** `src/pipeline/post_run_cleanup.py` (290 lines) has module-level path constants and a sequence of cleanup steps that all share knowledge of CWD. Could lift to a `Cleanup` class that takes CWD in `__init__`.

---

## Pattern 4: Decompose a God-Class

**When:** A single class has 20+ methods spanning multiple responsibilities. Common in GUI code, where one widget grows to handle layout + data + events + persistence over many small commits.

**Shape:** Identify responsibility clusters (UI vs. data vs. IO). Split into 2–4 focused classes that compose. The original class either becomes a thin orchestrator that wires the new classes together, or one of the new classes becomes the new entry point and the old class is removed.

**Gotchas:**
- Inheritance chains complicate this. If the class is subclassed, the split needs to preserve the public interface those subclasses depend on.
- PySide6 signal/slot connections are state; preserve them exactly. Disconnecting and reconnecting in a refactor is a common source of "the button stopped working" bugs.

**lil_bro example:** `src/gui/widgets/dashboard.py` (290 lines, just under threshold) is close to needing this if it grows further.

---

## Pattern 5: Extract a Registry

**When:** Multiple files have parallel `@register_*` decorators, or matching dispatch tables. The registry itself wants to be a module so all the registrations can be discovered.

**Shape:** Lift the registry (the `_REGISTRY` dict + `register_*` decorator + `dispatch_*` function) to its own module. Each registering file imports the decorator from there.

**Gotchas:**
- Import order matters — the registry module must be imported before any registering module, or registrations will be missing at dispatch time. Usually solved by importing all registering modules from one well-known entry point at startup.
- `src/pipeline/fix_dispatch.py` is already exactly this pattern. Use it as a model.

---

## Pattern 6: Separate Configuration from Behavior

**When:** Large constants tables (color palettes, setting maps, command tables, QSS strings) are interleaved with the code that consumes them, making the consuming code hard to read.

**Shape:** Move the constants to a sibling `_data.py` or `_config.py` module. The consuming module imports them.

**Gotchas:**
- If the constants reference other module symbols, you may need to invert the dependency.
- This is the cheapest refactor — almost no behavior-change risk. Good starter chunk for a multi-chunk plan to build confidence and CI green before riskier chunks land.

**lil_bro example:** `src/gui/theme/stylesheet.py` (794 lines) is heavy on QSS string constants. Splitting QSS-by-section into `_qss_card.py`, `_qss_button.py`, etc. is essentially this pattern. The QSS variables stay in `stylesheet.py` as the public API; section-specific QSS lives in private siblings.

---

## Picking a pattern from investigation bundles

| Signal in the investigation | Likely pattern |
|---|---|
| symbol-mapper found "all IO" cluster | Split IO from Logic |
| symbol-mapper found module-level state with many users | Lift State |
| symbol-mapper found 2+ cohesive clusters with low cross-cluster coupling | Extract Module (one per cluster) |
| symbol-mapper found a god-class | Decompose a God-Class |
| architecture-mapper found parallel registrations elsewhere | Extract a Registry |
| target file is mostly string/dict constants | Separate Config from Behavior |

---

## Special domains in lil_bro

### Files under `src/agent_tools/` or `src/pipeline/`
These touch the human-in-the-loop approval contract documented in CLAUDE.md (`prompt_approval()`, `start_session_manifest()`, `execute_fix()`). Refactors here must preserve the contract exactly — `agents/safety-reviewer.md` at `.claude/agents/safety-reviewer.md` exists specifically to check that. Flag any chunk touching these directories as needing a safety-reviewer pass *in addition to* the code-simplifier critic.

### Files under `src/gui/widgets/`
Any new module under here needs adding to `lil_bro.spec` `hiddenimports` per CLAUDE.md. The bundled exe will silently fail to find it otherwise. Flag this in the Phase 6 report.

### Files using Serena-managed symbols
The implementation worker must follow `references/serena-safety.md` to avoid LS desync. The plan's chunk list should pre-classify each chunk as symbol-only / mixed / wholesale-rewrite so the worker knows when to restart the LS.
