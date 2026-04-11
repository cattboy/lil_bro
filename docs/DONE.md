# lil_bro Refactoring — Progress Tracker

**Branch**: `refactor/priority-1-improvements`
**Plan source**: `docs/REFACTORING_PLAN.md`
**Last updated**: 2026-04-11 (Issue 1.5 + T-005 — PhaseResult)

---

## Completed (Priority 1 + Priority 2-A)

Priority 1 scope (9 files), Priority 2-A scope (7 files + 2 new test files), and Issue 1.3 are done. 388 tests pass, 0 regressions.

### Issue 1.1 — Phase 5 crashes when Phase 3 was skipped
**Fix**: Null guard at the top of `FinalBenchPhase.run()` before thermal checks.
- `src/pipeline/phase_final.py` — 4-line guard added
- `tests/test_phase_final.py` — 3 new tests (runner=None, thermal gate, happy path)

### Issue 2.1 — calculate_fps_cap duplicated in nvidia_profile.py and nvidia_profile_setter.py
**Fix**: Single canonical definition in `nvidia_profile_dumper.py`; both callers import from there.
- `src/collectors/sub/nvidia_profile_dumper.py` — authoritative `calculate_fps_cap()` added
- `src/agent_tools/nvidia_profile.py` — local definition removed, import updated
- `src/agent_tools/nvidia_profile_setter.py` — local definition removed, import updated
- `tests/test_nvidia_profile.py` — `test_setter_matches_analyzer` → `test_single_canonical_definition`

### Issue 2.3 — RuntimeError raised from setter code with no typed hierarchy
**Fix**: `SetterError(LilBroError)` added to errors.py; 3 raise sites in nvidia_profile_setter.py updated.
- `src/utils/errors.py` — `SetterError` class added
- `src/agent_tools/nvidia_profile_setter.py` — 3x `raise RuntimeError` → `raise SetterError`
- `tests/test_nvidia_profile.py` — `test_raises_on_import_failure` updated to expect `SetterError`

### Issue 3.2 — Thresholds and timeouts hardcoded across multiple files
**Fix**: `src/config.py` with typed dataclasses and optional `lil_bro_config.json` override.
- `src/config.py` — new file: `BenchmarkConfig`, `ThermalConfig`, `AppConfig`, `_load_config()`
- `tests/test_config.py` — 7 new tests (defaults, missing file, valid JSON, malformed, partial, empty)

### Issue 3.2 (config.py) — already listed above under Priority 1.

---

## Completed (Priority 2-A)

### T-004 — Type `PipelineContext.llm` properly
**Fix**: Added `from llama_cpp import Llama` to the `TYPE_CHECKING` block in `base.py`; changed field from `llm: object = None` to `llm: Optional[Llama] = None`.
- `src/pipeline/base.py` — 2-line change (import + annotation)

### Issue 1.2 — Context field defaults unconditionally pre-assigned in phase_baseline.py
**Fix**: Added `_SKIP_RESULT_HOT` named constant; moved the pre-assignment of `ctx.baseline_result` and `ctx.peak_temps` inside the `if benchmark_skipped:` block so the success path no longer overwrites stale sentinel values.
- `src/pipeline/phase_baseline.py` — `_SKIP_RESULT_HOT` added, 2 lines moved inside guard

### Issue 1.4 — Thermal guard pattern duplicated across both benchmark phases
**Fix**: Added `run_thermal_guard(phase_name, ctx, **kwargs) -> bool` combinator to `thermal_gate.py`. Phase 5 now calls this single function instead of two separate checks. Phase 3 retains the two-step explicit pattern to preserve the `ctx.runner is None` sentinel semantics.
- `src/pipeline/thermal_gate.py` — `run_thermal_guard()` added
- `src/pipeline/phase_final.py` — replaced 2-step thermal pattern with `run_thermal_guard`; import updated
- `tests/test_thermal_gate.py` — 4 new tests for `run_thermal_guard`
- `tests/test_phase_final.py` — 2 existing tests updated to patch `run_thermal_guard` (was `require_thermal_protection` / `thermal_safety_gate`)

### T-003 — DEVMODE struct duplicated in monitor_dumper.py and display_setter.py
**Fix**: Single canonical `DEVMODE` struct and `enum_raw_modes()` in `src/utils/display_utils.py`; both callers import from there.
- `src/utils/display_utils.py` — new file: `DEVMODE`, `enum_raw_modes()`, constants
- `src/collectors/sub/monitor_dumper.py` — local DEVMODE removed; imports from display_utils; `enum_display_modes()` delegates to `enum_raw_modes`
- `src/agent_tools/display_setter.py` — local DEVMODE and `_enum_all_modes()` removed; imports from display_utils; `find_best_mode()` uses `enum_raw_modes`
- `tests/test_display_utils.py` — new file: 5 tests (struct fields, constants, single canonical definition)

---

## Completed (Issue 1.3)

### Issue 1.3 — LLM typed as `object` / `Any` across pipeline pass-through sites
**Fix**: Added `TYPE_CHECKING` guard + `Optional[Llama]` annotations at all LLM pass-through sites; removed stray `dict[str, Any]` inline annotations.
- `src/pipeline/_state.py` — `_llm: Optional[Llama]`, `get_llm() -> Optional[Llama]`, `set_llm(instance: Optional[Llama]) -> None`
- `src/pipeline/phases.py` — `run_optimization_pipeline(llm: Optional[Llama] = None)`; `TYPE_CHECKING` guard added
- `src/llm/action_proposer.py` — `_call_llm(llm: Llama)`, `propose_actions(llm: Optional[Llama])`; `dict[str, Any]` → `dict` in `build_llm_input`

---

---

## Completed (Priority 3-A)

### Issue 3.5 — Circular import guard in integrity.py
**Fix**: Moved `from .formatting import ...` to module top level; removed two `try/except ImportError` blocks inside `verify_integrity()`. No actual circular dependency existed — `formatting.py` only imports `shutil`, `sys`, and `colorama`.
- `src/utils/integrity.py` — 2 lazy import blocks replaced by 1 top-level import

### Issue 1.6 — phase_config.py had zero error handling
**Fix**: Wrapped the entire analysis/proposal/approval block in `try/except`. `PipelineAborted` re-raises (user declined); all other `Exception` types are logged + warned, then swallowed so Phase 5 still runs.
- `src/pipeline/phase_config.py` — try/except added; unused `print_info` import removed
- `tests/test_phase_config.py` — new file: 2 tests (unexpected exception caught, PipelineAborted propagates)

### T-002 — UnicodeEncodeError on Windows CMD (CP437 terminals)
**Fix**: Added `sys.stdout.reconfigure(errors="replace")` early in `main()` via `isinstance` check. Non-encodable LLM output characters (e.g. curly quotes, em dashes) now print as `?` instead of crashing.
- `src/main.py` — 3-line guard added before any print calls
- `tests/test_formatting.py` — 1 new test: all `print_*` functions accept Unicode strings without raising

388 → 391 tests passing.

---

## Completed (Priority 2-B)

### Issue 2.4 (scoped) — Unified subprocess wrapper
**Fix**: Created `src/utils/subprocess_utils.py` with `run_subprocess()` — thin `subprocess.run()` wrapper with consistent 10s default timeout and debug logging. Migrated 6 call sites in 3 files; complex Popen/polling patterns (cinebench, lhm_sidecar, dxdiag) deliberately left unchanged.
- `src/utils/subprocess_utils.py` — new file: `run_subprocess()` with timeout, debug logging, re-raises on error
- `src/agent_tools/power_plan.py` — 4 calls migrated; `run_subprocess` imported
- `src/collectors/sub/nvidia_smi_dumper.py` — 1 call migrated; gains default 10s timeout
- `src/collectors/sub/amd_smi_dumper.py` — 1 call migrated; gains 10s timeout (was unbounded)
- `tests/test_subprocess_utils.py` — new file: 6 tests (happy path, non-zero rc, timeout, FileNotFoundError, CalledProcessError, custom timeout)
- `tests/test_power_plan.py` — 5 mock patches updated from `subprocess.run` → `run_subprocess`

**Skipped sub-issues** (per eng-review scope):
- `CollectorResult` generic type — explicitly deferred, codebase not grown enough to justify
- Full specs schema / TypedDict — over-engineered for a 4 K-line solo tool

391 → 397 tests passing.

---

## Completed (Config auto-generation)

### Issue 3.2 (follow-up) — Auto-generate lil_bro_config.json on first run
**Fix**: On first run (no config file in CWD), the app uses hardcoded defaults. At exit, `save_default_config()` writes a JSONC template with `//` comment descriptions for every setting. Subsequent runs read from the file. Existing files are never overwritten.
- `src/config.py` — replaced `_get_exe_dir()` with CWD-based `get_config_path()`; added `_strip_jsonc()` for JSONC comment stripping; added `_DEFAULT_CONFIG_TEMPLATE` + `save_default_config()`
- `src/main.py` — `save_default_config()` call added to `finally` block (before cleanup)
- `.gitignore` — `lil_bro_config.json` added
- `tests/test_config.py` — 5 existing tests updated (`_get_exe_dir` mock → `monkeypatch.chdir`); 10 new tests (JSONC stripping, save/no-overwrite, round-trip, error resilience, completeness)

397 → 407 tests passing.

---

## Completed (Issue 1.5 + T-005)

### Issue 1.5 + T-005 — PhaseResult return type
**Fix**: Added `PhaseResult` dataclass to `base.py`; updated all 5 phase `run()` methods to return it; orchestrator in `phases.py` now captures and logs non-completed results.
- `src/pipeline/base.py` — `PhaseResult` dataclass added (`status`, `message`, `error`); `Phase` protocol updated to `-> PhaseResult`; `Literal` import added
- `src/pipeline/phases.py` — orchestrator loop captures `PhaseResult`; logs skipped/failed phases via debug logger
- `src/pipeline/phase_bootstrap.py` — returns `PhaseResult("completed", ...)` or `PhaseResult("completed", ..., error=...)` after restore-point failure + user override
- `src/pipeline/phase_scan.py` — returns `PhaseResult("completed", ...)`; unused `print_warning` import removed
- `src/pipeline/phase_baseline.py` — returns `PhaseResult("skipped", ...)` on thermal/temp gates; `PhaseResult("completed", ...)` on success
- `src/pipeline/phase_config.py` — returns `PhaseResult("skipped", ...)` on no specs; `PhaseResult("failed", ..., error=...)` on unexpected exception; `PhaseResult("completed", ...)` on success
- `src/pipeline/phase_final.py` — returns `PhaseResult("skipped", ...)` on null runner or thermal gate; `PhaseResult("completed", ...)` on success
- `tests/test_phase_final.py` — 3 existing tests updated to assert on `PhaseResult.status`
- `tests/test_phase_config.py` — exception test updated to assert `status == "failed"` and `error is not None`

407 → 407 tests passing (no new tests needed — existing tests now assert on PhaseResult).

---

## Outstanding

### Priority 3 (Nice to Have)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| 2.5 | Setter interface contract missing — each setter has a different signature (out of scope per eng-review) | All setter files, `fix_dispatch.py` | M |
| 3.3 | Observability/metrics missing — no timing, no success ratio, no aggregation | N/A | L |
| 3.4 | Lifecycle management split — LHM and ThermalMonitor ownership unclear | `main.py`, `lhm_sidecar.py`, `phase_*.py` | M |
| T-001 | Future-proof formatting.py for GUI backend | `formatting.py` | M |

---

## Explicitly Out of Scope (decisions from eng-review + Priority 2-B analysis)

- **Setter interface Protocol** — `display_setter.py`'s `(bool, str)` return is intentional (dry_run/apply two-phase pattern). Not changing.
- **Phase Dependency Framework** (PhaseContract/PhaseResult classes) — over-engineered for a 4,000-line solo tool. Null guard in phase_final.py is sufficient.
- **Unified CollectorResult generic type** — deferred; codebase not grown enough to justify.
- **FallbackStrategy Protocol** (Issue 3.1) — the four fallback paths (LLM static templates, Cinebench CPU stress, model_loader None, thermal empty dict) have different triggers, return types, and caller patterns. A unified abstraction would add indirection without reducing complexity. Individual paths are tested and documented. Closed.
