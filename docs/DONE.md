# lil_bro Refactoring — Progress Tracker

**Branch**: `refactor/priority-1-improvements`
**Plan source**: `docs/REFACTORING_PLAN.md`
**Last updated**: 2026-04-07

---

## Completed (Priority 1)

All 9 files in the Priority 1 scope are done. 377 tests pass, 0 regressions.

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

---

## Outstanding

### Priority 2 (Should Do)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| 1.2 | Context field defaults scattered — `ctx.baseline_result` and `ctx.peak_temps` initialized in multiple places | `phase_baseline.py`, `base.py` | XS |
| 1.3 | LLM stored as `object` in global `_state.py` — untestable, weakly typed | `_state.py`, `menu.py`, `phase_config.py` | S |
| 1.4 | Thermal duplicate pattern in phase_baseline and phase_final — both call `require_thermal_protection()` with identical pattern | `phase_baseline.py`, `phase_final.py`, `thermal_gate.py` | S |
| 2.2 | DEVMODE struct + mode enumeration duplicated in display_setter and monitor_dumper | `display_setter.py`, `monitor_dumper.py` | S |
| 2.4 | No CollectorResult type, no unified subprocess wrapper, no specs schema | Multiple | M |
| 3.1 | Fallback logic scattered — LLM, Cinebench, model, thermal each have separate ad-hoc fallback paths | Multiple | M |
| T-003 | DEVMODE struct dedup (see TODOS.md) | `display_setter.py`, `monitor_dumper.py` | S |
| T-004 | Type `PipelineContext.llm` properly — currently `object` (see TODOS.md) | `base.py` | XS |

### Priority 3 (Nice to Have)

| ID | Issue | Files | Effort |
|----|-------|-------|--------|
| 1.5 | Phase execution status not visible to orchestrator — no ran/skipped/failed signal | `phases.py` | S |
| 1.6 | Error handling inconsistent across phases — some catch, some don't | All `phase_*.py` | M |
| 2.5 | Setter interface contract missing — each setter has a different signature | All setter files, `fix_dispatch.py` | M |
| 3.3 | Observability/metrics missing — no timing, no success ratio, no aggregation | N/A | L |
| 3.4 | Lifecycle management split — LHM and ThermalMonitor ownership unclear | `main.py`, `lhm_sidecar.py`, `phase_*.py` | M |
| 3.5 | Circular import guard in integrity.py (lazy import to avoid cycle) | `integrity.py` | XS |
| T-001 | Future-proof formatting.py for GUI backend (see TODOS.md) | `formatting.py` | M |
| T-002 | Harden LLM output against UnicodeEncodeError on Windows CMD (see TODOS.md) | `formatting.py` | S |
| T-005 | Phase.run() return PhaseResult instead of None (see TODOS.md) | `phases.py`, all `phase_*.py` | S |

---

## Explicitly Out of Scope (decisions from eng-review)

- **Setter interface Protocol** — `display_setter.py`'s `(bool, str)` return is intentional (dry_run/apply two-phase pattern). Not changing.
- **Phase Dependency Framework** (PhaseContract/PhaseResult classes) — over-engineered for a 4,000-line solo tool. Null guard in phase_final.py is sufficient.
- **Unified CollectorResult generic type** — deferred to Priority 2 if/when the codebase grows.
- **FallbackStrategy Protocol** — deferred; individual fallback paths work and are tested.
