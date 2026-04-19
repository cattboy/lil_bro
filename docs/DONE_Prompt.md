# lil_bro — Opus Development Brief v2

**Version:** 2.0  
**Date:** 2026-04-19  
**Purpose:** Onboarding prompt for Opus. Read this in full before writing a single line of code.

---

## Your Role

You are continuing development of **lil_bro** — a local, privacy-first Windows gaming PC optimizer. It scans hardware configurations, detects misconfigurations, applies targeted fixes with explicit user approval, and can fully revert all changes. 100% offline. No data leaves the device.

**Hard constraint:** Every system modification requires `prompt_approval()` before executing. This is a safety contract, not a preference. Do not bypass it.

---

## Architecture

### Entry points
`src/main.py` → `src/pipeline/phases.py` → 5 phase files → `src/agent_tools/` checks

### 5-Phase Pipeline

| Phase | File | Role |
|-------|------|------|
| 1 Bootstrap | `phase_bootstrap.py` | Admin check, System Restore Point |
| 2 Scan | `phase_scan.py` | Hardware collection (LHM sidecar, WMI, registry, nvidia-smi) |
| 3 Baseline | `phase_baseline.py` | Pre-fix Cinebench or CPU stress benchmark |
| 4 Config | `phase_config.py` | Analyzer → LLM proposals → user approval → fix dispatch |
| 5 Final | `phase_final.py` | Post-fix benchmark + delta comparison |

### Key modules

| Module | Purpose |
|--------|---------|
| `src/pipeline/fix_dispatch.py` | `@register_fix` decorator registry; all `_fix_*` handlers |
| `src/utils/revert.py` | Session manifest read/write + per-fix revert functions |
| `src/pipeline/phase_revert.py` | Revert flow terminal UX |
| `src/utils/platform.py` | `is_admin()`, Windows OS helpers |
| `src/config.py` | Typed `AppConfig` dataclass + `lil_bro_config.json` override |
| `src/utils/action_logger.py` | User-facing audit trail (not debug logging) |
| `src/benchmarks/thermal_monitor.py` | `ThermalMonitor` — context manager, `derive_cpu_temp` |
| `src/utils/subprocess_utils.py` | `run_subprocess()` — 10 s default timeout, debug logging |
| `src/utils/display_utils.py` | Canonical `DEVMODE` struct + `enum_raw_modes()` |

### Fix dispatch pattern (critical — do not change)

Every `_fix_*` handler in `fix_dispatch.py` follows a two-phase structure:

```python
# Phase 1: action — raises → return False
try:
    result = do_action()
    if not result:
        return False
except Exception as e:
    print_error(...)
    return False

# Phase 2: manifest — own try/except, never masks fix result
try:
    append_fix_to_manifest({...})
except Exception as e:
    print_warning(f"[check] Fix applied but revert log failed: {e}")

print_success(...)
return True
```

Manifest write is always after a confirmed successful fix. Manifest failure warns but never fails the fix.

---

## Completed Foundation

The codebase went through a full audit + two refactoring sprints. **Do not re-implement any of this.** Verify current state with Serena before touching these areas.

### Structural (high impact)

| Work | Result |
|------|--------|
| Phase decomposition | `phases.py` split into 5 `phase_*.py` files; each returns `PhaseResult(status, message, error)` |
| Fix dispatch | `@register_fix` decorator; two-phase action/manifest pattern across all 5 handlers |
| Thermal deduplication | `derive_cpu_temp()` canonical in `thermal_guidance.py`; `ThermalMonitor` context manager |
| DEVMODE deduplication | `src/utils/display_utils.py` — canonical struct + `enum_raw_modes()` |
| Platform layer | `src/utils/platform.py` — `is_admin()` replaces 3 independent copies |
| Subprocess wrapper | `run_subprocess()` — unified timeout + debug logging across 6 call sites |
| Config system | `AppConfig` typed dataclasses; auto-generates `lil_bro_config.json` on first run |
| PhaseResult | All 5 phases return typed result; orchestrator logs non-completed phases |
| ThermalMonitor CM | `__enter__`/`__exit__` ensures cleanup on unexpected exceptions |
| ActionLogger | `threading.Lock` + injectable `echo_fn` — no more inline `print_dim` imports |

### Bug fixes

| Bug | Fix |
|-----|-----|
| LHM dual lifecycle | `LHMSidecar()` removed from `phases.py`; startup instance passed through |
| Cinebench zombie | `subprocess.Popen([exe, flag])` — no `shell=True`; process PID captured |
| `attempt` scope leak | `attempt = 0` initialised before `for` loop in `startup_thermals.py` |
| Cleanup silent swallow | `except Exception: pass` replaced with `debug_logger.warning(...)` |
| NPI power_mgmt ID | Corrected to `0x1057EB71`; all `SETTING_IDS` converted to hex literals |
| Manifest write ordering | Manifest written after fix succeeds, in isolated `try/except` |

### Code quality

| Item | Fix |
|------|-----|
| LLM typing | `Optional[Llama]` throughout pipeline; `TYPE_CHECKING` guard pattern |
| `_UNICODE_SAFE` | Renamed to `_ASCII_FALLBACK` (semantics corrected) |
| Progress bar branches | Unicode/ASCII conditionals use `_ASCII_FALLBACK` correctly |
| `_REPO_ROOT` | `Path(__file__).resolve().parent…` (pathlib, not `os.path.join`) |
| LLM retry logging | `except Exception: pass` replaced with `debug_logger` call |
| Dead `poll_count` | Removed from `mouse.py` |
| Circular import | `integrity.py` lazy imports replaced with top-level import |
| `phase_config` error handling | Unexpected exceptions caught + logged; `PipelineAborted` still propagates |
| UnicodeEncodeError | `sys.stdout.reconfigure(errors="replace")` in `main.py` |
| `_derive_cpu_temp` | Made public (`derive_cpu_temp`); `ThermalMonitor` now calls it instead of reimplementing |

---

## Active Work — In Progress

### Branch: `fix/manifest-write-isolation`
Two-phase fix/manifest pattern applied to all 5 `_fix_*` handlers in `fix_dispatch.py`. **Must be merged to `feature/revert-last-session` and `main` before any other work proceeds.**

### Branch: `feature/revert-last-session`
Revert feature partially implemented. `phase_revert.py` exists and has been modified. Core `revert.py` may be partially wired. The manifest infrastructure is live — fix handlers are already writing session data — but the consumption path (menu option 4, `--revert` flag, revert flow) is not yet complete.

See `docs/completed/plan-revert-feature.md` for full schema, UX mockups, and test requirements.

---

## Prioritized Implementation Queue

### Priority scale

| Tier | Criteria | When to act |
|------|----------|-------------|
| **P0 — Finish now** | In-progress feature; half-built safety features erode user trust and leave the system in inconsistent state | Before starting anything else |
| **P1 — Next sprint** | User-visible or build-critical; clear benefit, low regression risk | After P0 is merged and tested |
| **P2 — Schedule** | Code quality win; meaningful but no user impact until a later phase | When a sprint has capacity |
| **P3 — Defer** | Blocked on an unresolved prerequisite, or ROI only materializes at scale | Revisit when prerequisite is met |

---

### P0 — Finish first: Revert Feature

**Severity:** The session manifest is live and writing data on every run. Users have no way to consume it yet. A safety feature with no UI is a liability.

**Implementation order:**

1. **Merge `fix/manifest-write-isolation` → `feature/revert-last-session`**
   Manifest write isolation is a prerequisite; the revert flow assumes the manifest is only written on confirmed success.

2. **Verify `src/utils/revert.py`** — confirm all five functions exist per spec:
   - `start_session_manifest(restore_point_created: bool) -> None`
   - `append_fix_to_manifest(entry: dict) -> None`
   - `load_manifest() -> dict | None`
   - `revert_fix(entry: dict) -> tuple[bool, str]`
   - `trigger_system_restore(session_date: str) -> bool`

3. **Complete `src/pipeline/phase_revert.py`** — terminal UX flow:
   - Load manifest → empty-state exit if missing
   - Summary screen: revertible vs cannot-revert sections
   - `prompt_approval("Revert N changes?")`
   - Reverse-order revert loop with per-fix `[OK]` / `[FAIL]` progress
   - Partial-failure path → offer System Restore Point

4. **Wire entry points:**
   - `src/pipeline/menu.py` — option 4 "Revert last session"
   - `src/main.py` — `--revert` CLI flag (argparse)
   - `src/pipeline/approval.py` — `start_session_manifest()` call just before fix loop

5. **Tests (~22):** See `docs/completed/plan-revert-feature.md` § Testing Requirements.

**Per-fix revert dispatch:**

| Fix key | Revert method |
|---------|---------------|
| `power_plan` | `powercfg /setactive <before.guid>` |
| `game_mode` | `winreg.SetValueEx(... before.AutoGameModeEnabled)` |
| `nvidia_profile` | `npi.exe -importProfile <before_backup_path>` |
| `display` | `ChangeDisplaySettingsEx` with before `DEVMODE` |
| `temp_folders` | Non-revertible — display note only |

---

### P1 — Next sprint: Multi-arch PawnIO build

**T-007 | Effort: M | Risk: Low**

`PawnIO_setup.exe` is a multi-arch installer (x64 + ARM64 `.sys` files embedded). Currently only the x64 variant is kept; the ARM64 file is discarded. An ARM64 lil_bro build would re-extract a file we already had.

**Severity:** Additive — x64 path is completely unchanged. Risk is near-zero.

**Implementation:**

1. **`tools/PawnIO_Latest_Check/update_pawnio.ps1`**
   - Step 0 guard: check both `resources/extracted/x64/PawnIO.sys` AND `resources/extracted/arm64/PawnIO.sys` for correct machine types before short-circuiting
   - Step 7: after selecting x64 variant, also copy arm64 variant to its subfolder
   - Final copy uses `--arch` parameter (default: `x64`)

2. **`build.py`**
   - Add `--arch` flag (`choices=["x64", "arm64"]`, `default="x64"`)
   - Pre-build: copy `resources/extracted/<arch>/PawnIO.sys` → `tools/PawnIO/dist/PawnIO.sys`

3. **`.gitignore`** — add `/tools/PawnIO_Latest_Check/resources/extracted/`

**Acceptance:** `python build.py` identical to today. `python build.py --arch arm64` embeds ARM64 driver. Re-run with both subfolders present is a no-op.

---

### P2 — Schedule: `formatting.py` API for GUI backend

**T-001 | Effort: L | Risk: Low | Blocked by: GUI architecture decision**

Add `return_str: bool = False` parameter to all `print_*` functions in `src/utils/formatting.py`. When `True`, return the formatted string instead of printing. The terminal path stays unchanged; the future GUI backend calls with `return_str=True`.

**Do not implement until the GUI architecture (PyQt / Phase 5) is scoped.** Adding the parameter now creates dead code with no consumer. When the GUI is scoped, implement this immediately — it is a prerequisite for every GUI widget that displays system status.

---

### P3 — Defer: Observability & Instrumentation

**T-006 | Effort: L | Blocked by: scale**

Phase timing snapshots, per-check success/failure ratios, metrics aggregation via `@instrument` decorator or metrics registry. No current user-visible benefit for a single-contributor CLI tool. Revisit when the codebase or team grows.

---

## Implementation Principles

These apply to every change in every PR. Non-negotiable.

1. **Human-in-the-loop:** `prompt_approval()` before every system modification. No silent changes, ever.
2. **Fix/manifest two-phase:** Action succeeds first; manifest write is isolated in its own `try/except`. Manifest failure warns but never fails the fix and never masks fix success.
3. **Fallback chain:** Never hard-fail when a tool is missing. WMI and registry are fallbacks for nvidia-smi, dxdiag, etc.
4. **Temp files in CWD:** `get_temp_dir()` from `src/utils/paths.py` as `dir=` arg — never system `%TEMP%`.
5. **Serena for Python:** `mcp__serena__*` tools for all `.py` reads and edits. Built-in Read/Grep/Glob/Edit on `.py` files are disallowed when Serena is running.
6. **uv, not pip:** `uv pip install` for all package installs. Never `pip install` directly.
7. **Test gate:** Every PR must maintain or grow the passing test count. Run `source .venv/Scripts/activate && python -m pytest tests/ -q` before declaring done.
8. **No silent failures:** `except Exception: pass` is banned. Log to `debug_logger`, warn to user, or re-raise. Choose deliberately.
