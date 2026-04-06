# lil_bro Technical Audit v2

Comprehensive code review covering every `.py` file under `src/`. Each finding is validated against the actual source — no speculative claims. Organized into implementation-ready work packages.

---

## Part A — Confirmed Bugs

### BUG-1: LHM Sidecar Dual Lifecycle (Severity: Medium)

**Files:** `main.py:49-65`, `phases.py:33-41`, `post_run_cleanup.py:151-165`

**Problem:** Two independent `LHMSidecar` instances manage the same process:
1. `main.py:65` — `startup_lhm, _ = run_startup_thermal_scan()` creates sidecar #1, held until `post_run_cleanup(startup_lhm)` at exit.
2. `phases.py:35` — `lhm = LHMSidecar()` creates sidecar #2, stopped in its own `finally` block at line 41.

Because `LHMSidecar.start()` detects port 8085 is occupied and sets `_already_running = True`, sidecar #2 is a no-op wrapper that "attaches" without launching anything. But sidecar #2's `stop()` in `phases.py:41` then becomes a silent no-op (it skips kill because `_already_running=True`). Meanwhile `post_run_cleanup` stops sidecar #1 correctly. This *works by accident* but:
- Creates confusion about who owns the LHM lifecycle.
- If `run_optimization_pipeline()` is ever called multiple times from the menu (it can be — menu_loop is a `while True`), each call creates another dangling `LHMSidecar` object.

**Fix:** Pass the startup LHM instance into the pipeline instead of creating a new one. Remove the `LHMSidecar()` construction from `phases.py`.

---

### BUG-2: `startup_thermals.py` — `attempt` Variable Scope Leak (Severity: Low)

**File:** `startup_thermals.py:57-67`

```python
for attempt in range(_SENSOR_RETRIES):  # line 57
    temps = fetch_snapshot()
    if temps:
        break
    ...

if attempt > 0:  # line 66 — uses loop variable AFTER the for block
    print_step_done(bool(temps))
```

The `attempt` variable leaks from the `for` loop scope. This works today only because `_SENSOR_RETRIES = 10` is hardcoded. If it were ever set to `0` (e.g., via a config override), `attempt` would be `NameError: name 'attempt' is not defined`.

**Fix:** Initialize `attempt = 0` before the loop, or restructure to avoid depending on the loop variable after exit.

---

### BUG-3: Cinebench Zombie Process on Timeout (Severity: High)

**File:** `cinebench.py:184-219`

```python
cmd = (
    f'start /b /wait "parentconsole" '
    f'"{self.cinebench_path}" {cb_flag}'
)
result = subprocess.run(
    cmd, shell=True, capture_output=True,
    text=True, timeout=_CINEBENCH_TIMEOUT,
)
```

When the 10-minute timeout fires, `subprocess.run` kills the **shell wrapper** (`cmd.exe /c start /b /wait ...`), NOT the actual `Cinebench.exe` process. The Cinebench process — which is a CPU-heavy benchmark — continues running in the background consuming 100% of all cores indefinitely.

**Fix:** Launch `Cinebench.exe` directly via `subprocess.Popen` (no `shell=True`, no `start /b`). Capture the PID. On timeout, use `proc.kill()` followed by `taskkill /F /T /PID` as a safety net (same pattern already used in `lhm_sidecar.py:315-335`).

---

### BUG-4: Cleanup Silently Swallows All Exceptions (Severity: Medium)

**File:** `post_run_cleanup.py:157-179`

```python
# 1. Kill the LHM sidecar process
if lhm is not None:
    try:
        lhm.stop()
    except Exception:
        pass          # <-- silently swallowed

# 2. Uninstall PawnIO kernel driver + service + registry
try:
    _uninstall_pawnio()
except Exception:
    pass              # <-- silently swallowed

# 3. Remove CWD ./lil_bro/ temp folder
try:
    _cleanup_cwd_tempdir()
except Exception:
    pass              # <-- silently swallowed
```

The design intent is correct (cleanup must never mask the original error), but `pass` means a failed PawnIO uninstall or a failed driver file deletion leaves behind a **kernel driver on the user's system** with zero evidence. The user won't know the driver persists.

**Fix:** Replace `pass` with `get_debug_logger().warning(...)`. The debug logger is already no-op when `--debug` isn't passed, so there's zero overhead in normal runs, but failures become visible when debugging.

---

## Part B — Code Duplication & Hygiene

### DUP-1: `is_admin()` Implemented 3 Times

| Location | Signature |
|---|---|
| `bootstrapper.py:10` | `is_admin() -> bool` |
| `post_run_cleanup.py:32` | `_is_admin() -> bool` |
| `lhm_sidecar.py:54` | `_is_admin() -> bool` |

All three do the same `ctypes.windll.shell32.IsUserAnAdmin()` call. One canonical version should live in `utils/` and be imported everywhere.

**Proposed location:** `src/utils/platform.py` (new file — also hosts other OS-level helpers, see REFACTOR-4).

---

### DUP-2: `specs` File Read Twice in `phases.py`

**File:** `phases.py:71-77` and `phases.py:131-138`

`full_specs.json` is opened, read, and parsed with `json.load()` at **two** separate points in the same function:
- Line 75: To display the hardware preview in Phase 2
- Line 134: To feed into the check analyzers in Phase 4

**Fix:** Read once and store in a local variable.

---

### DUP-3: `_derive_cpu_temp` Logic Duplicated

**Files:** `thermal_guidance.py:141-169`, `thermal_monitor.py:179-204`

`ThermalMonitor.get_cpu_peak()` reimplements the same priority-ordered CPU sensor selection logic (`CPU Package -> Tctl/Tdie -> safe sensors`) that lives in `thermal_guidance._derive_cpu_temp()`. The code comment even says *"Uses the same priority order as thermal_guidance._derive_cpu_temp"*.

**Fix:** Have `ThermalMonitor.get_cpu_peak()` call `thermal_guidance._derive_cpu_temp(self._peak_temps)` directly. Make `_derive_cpu_temp` a public function (rename to `derive_cpu_temp`).

---

## Part C — Architectural Refactors

### REFACTOR-1: Decompose `phases.py` (Impact: High, Risk: Medium)

**File:** `phases.py` — 220 lines, 27 imports, handles all 5 pipeline phases in a single function.

**Current state:** `_run_pipeline()` is a monolithic sequential function mixing:
- Restore point creation (Phase 1)
- LHM lifecycle + spec dump + display (Phase 2)
- Benchmark orchestration + thermal monitoring (Phase 3)
- Check analyzers + LLM proposals + approval flow (Phase 4)
- Final benchmark + comparison (Phase 5)

**Proposed approach:** A lightweight `Phase` protocol — no need for a full framework:

```python
# pipeline/base.py
from typing import Protocol

class PipelineContext:
    """Bag of shared state passed between phases."""
    lhm: LHMSidecar
    thermal: ThermalMonitor
    specs: dict
    baseline: dict
    # ...

class Phase(Protocol):
    def run(self, ctx: PipelineContext) -> None: ...
```

Each phase becomes its own file (`phase_bootstrap.py`, `phase_scan.py`, etc.), and `phases.py` reduces to:

```python
PHASES = [BootstrapPhase(), ScanPhase(), BaselineBenchPhase(), ConfigPhase(), FinalBenchPhase()]
for phase in PHASES:
    phase.run(ctx)
```

**NOTE:** This is the largest change. It touches 1 file (split into 6) and all imports into `phases.py`. Recommend doing this **last** after smaller fixes are stable.

---

### REFACTOR-2: Decorator-Based Fix Registry (Impact: Medium, Risk: Low)

**File:** `fix_dispatch.py`

Currently each fix handler is defined in `fix_dispatch.py` and manually registered in the `FIX_REGISTRY` dict at the bottom. The actual logic they call (e.g., `set_game_mode`, `clean_temp_folders`) lives in `agent_tools/`. This means adding a new fixable check requires edits in **two** files.

**Proposed approach:** A decorator in `fix_dispatch.py`:

```python
FIX_REGISTRY: dict[str, Callable] = {}

def register_fix(check_name: str):
    def decorator(fn):
        FIX_REGISTRY[check_name] = fn
        return fn
    return decorator
```

Each `_fix_*` function uses `@register_fix("check_name")` and stays in `fix_dispatch.py`. This is a small, safe refactor — not a plugin system, just eliminating the manual registration step.

**TIP:** This does **not** move fix handlers into `agent_tools/`. Keeping them in `fix_dispatch.py` is correct — they're thin wrappers that do imports + error handling + logging. The decorator just replaces the manual dict.

---

### REFACTOR-3: Pipeline Context via Dependency Injection (Impact: Medium, Risk: Low)

**Files:** `_state.py`, `phases.py:184`, `menu.py:67-74`

The LLM instance is stored in a module-level global (`_state.py:_llm`) accessed via `get_llm()`/`set_llm()`. This works but makes testing awkward (must mock module state) and is the only module-level mutable global in the codebase.

**Proposed approach:** The `PipelineContext` dataclass from REFACTOR-1 naturally absorbs this. If REFACTOR-1 is deferred, a simpler step is to pass `llm` as an argument to `run_optimization_pipeline()` and thread it through to `propose_actions()`.

---

### REFACTOR-4: Platform Abstraction Layer (Impact: Low, Risk: Low)

**Problem:** 14 call sites use `ctypes.windll` directly, 4 files `import winreg` at the top level. This makes the project impossible to import-test on Linux/CI without mocking at module load time.

| OS binding | Files |
|---|---|
| `ctypes.windll.shell32` | bootstrapper.py, lhm_sidecar.py, post_run_cleanup.py |
| `ctypes.windll.user32` | formatting.py, mouse.py, display_setter.py, monitor_dumper.py |
| `ctypes.windll.kernel32` | formatting.py, post_run_cleanup.py |
| `import winreg` | game_mode.py, pawnio_check.py, monitor_dumper.py, post_run_cleanup.py |

**Proposed approach:** Create `src/utils/platform.py` with a simple abstraction:

```python
# src/utils/platform.py
import sys

IS_WINDOWS = sys.platform == "win32"

def is_admin() -> bool:
    if not IS_WINDOWS:
        return False
    import ctypes
    return bool(ctypes.windll.shell32.IsUserAnAdmin())
```

This consolidates the 3 `is_admin` duplicates and makes CI imports possible. The `winreg`-using modules should use lazy imports (`import winreg` inside functions, not at module top level) since they already guard their logic with try/except.

**NOTE:** This is NOT about cross-platform support. lil_bro is Windows-only. This is about making the codebase importable on CI runners and reducing duplication. Modules like `game_mode.py` and `pawnio_check.py` that `import winreg` at the top level crash on import on Linux, making test infrastructure harder.

---

### REFACTOR-5: ActionLogger — Targeted Improvements (Impact: Low, Risk: Low)

**File:** `action_logger.py`

**v1 audit correction:** The v1 audit suggested replacing ActionLogger with Python's `logging` module. After reviewing the code, this is **not advisable**. ActionLogger serves a distinct purpose — it's a user-facing audit trail of system modifications (restore points created, power plans switched, files deleted). It is NOT diagnostic debug logging (that's `debug_logger.py`, which already uses `logging`). Conflating these two would muddy both.

**Actual issues with ActionLogger:**
1. **No thread safety** — multiple threads (thermal monitor, progress bar animation) could theoretically write concurrently. The file handle is opened/closed per write, which is safe on most OSes but not guaranteed.
2. **Circular import pattern** — `log_session_start()` and `log_action()` both do `from src.utils.formatting import print_dim` inside the method body to avoid circular imports. This is a symptom of tight coupling between logging and display.

**Fix:**
1. Add a `threading.Lock` to `ActionLogger.__init__` and acquire it around file writes.
2. Accept an optional `echo_fn: Callable[[str], None]` in the constructor instead of importing `print_dim` inline. Default to a no-op; `main.py` can inject `print_dim` at startup.

---

## Part D — Minor Quality Issues

| # | File | Issue | Fix |
|---|---|---|---|
| Q-1 | `formatting.py:10` | `_UNICODE_SAFE` logic is inverted — `True` when encoding is NOT utf-8, used to select ASCII fallbacks. Name suggests the opposite. | Rename to `_ASCII_FALLBACK` |
| Q-2 | `progress_bar.py:52-61` | Unicode/ASCII character sets are swapped — `_UNICODE_SAFE=True` (which means non-UTF-8) gets the Unicode chars | Fix the conditional branches (swap the if/else) |
| Q-3 | `cinebench.py:28` | `_REPO_ROOT` computed via `os.path.join(os.path.dirname(__file__), "..", "..")` — fragile path arithmetic | Use `pathlib.Path(__file__).resolve().parent.parent` |
| Q-4 | `action_proposer.py:110` | `except Exception: pass` in LLM retry loop — silently swallows model errors | Log to debug_logger |
| Q-5 | `mouse.py:17` | `poll_count` variable declared but never used | Remove dead variable |

---

## Part E — Implementation Tiers

### Tier 1 — Quick Wins (est. 1-2 hours, safe to do independently)

| Item | Description |
|---|---|
| BUG-2 | Initialize `attempt = 0` before loop in startup_thermals.py |
| BUG-4 | Replace `pass` with `get_debug_logger().warning(...)` in post_run_cleanup.py |
| DUP-2 | Read specs file once in phases.py |
| DUP-3 | Make `_derive_cpu_temp` public, call it from `ThermalMonitor.get_cpu_peak()` |
| Q-1 | Rename `_UNICODE_SAFE` to `_ASCII_FALLBACK` |
| Q-2 | Fix swapped Unicode/ASCII branches in progress_bar.py |
| Q-3 | Use pathlib for `_REPO_ROOT` |
| Q-4 | Add debug logging to LLM retry |
| Q-5 | Remove dead `poll_count` variable |

### Tier 2 — Structural Fixes (est. 2-3 hours, moderate dependency chain)

| Item | Description |
|---|---|
| BUG-1 | Pass startup LHM into pipeline; remove duplicate construction in phases.py |
| BUG-3 | Rewrite Cinebench launch to use `Popen` without `shell=True` |
| DUP-1 | Consolidate `is_admin` into new `src/utils/platform.py` |
| REFACTOR-2 | Add `@register_fix` decorator to fix_dispatch.py |
| REFACTOR-4 | Create `platform.py`, move `winreg` imports to lazy/inline where needed |
| REFACTOR-5 | Add thread lock + injectable echo callback to ActionLogger |

### Tier 3 — Architecture (est. 4+ hours, should follow Tier 1+2)

| Item | Description |
|---|---|
| REFACTOR-1 | Decompose `phases.py` into Phase protocol + 5 phase files |
| REFACTOR-3 | Introduce `PipelineContext` dataclass, eliminate `_state.py` global |

---

## Verification Plan

### Automated
- Run existing test suite: `python -m pytest tests/ -v`
- After Tier 2: confirm Cinebench launches and terminates cleanly on timeout (manual test on Windows)
- After REFACTOR-1: all 25 existing test files must pass unchanged

### Manual
- After BUG-1 fix: run the pipeline twice from the menu without restarting — verify only one LHM process exists
- After BUG-3 fix: trigger Cinebench timeout (set `_CINEBENCH_TIMEOUT = 5`) and confirm `tasklist` shows no orphaned `Cinebench.exe`

---

## Open Questions

1. **Tier priority:** Should I start with Tier 1 (quick wins) and work up, or do you want to tackle Tier 2 items like the Cinebench zombie fix first?
2. **Q-2 (progress_bar.py):** The Unicode/ASCII branches appear swapped. Can you confirm — does your target Windows Terminal render the block chars correctly, or does it need the ASCII fallback?
3. **REFACTOR-1 scope:** Do you want the Phase decomposition to use a formal `Protocol` class, or just split `_run_pipeline()` into 5 named functions in separate files (simpler, less abstraction)?
