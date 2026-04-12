# TODOS

Items flagged during reviews but deferred from current PRs.
Format: Priority | Effort (human / CC) | Context

---

## Open

### T-001 — Future-proof formatting.py API for rich/GUI backend
**Priority:** P2
**Effort:** L human / M with CC
**Why:** All `print_*` functions in `formatting.py` call `print()` directly and are tightly coupled to colorama. When the PyQt GUI arrives (planned, deferred), a GUI layer would need to intercept terminal output and display it in a widget instead. A `return_str=False` default param on each function enables this without changing any call sites.
**How to apply:** Add `return_str: bool = False` param to all print_* functions. When `True`, return the formatted string instead of printing. The GUI backend calls them with `return_str=True`; the terminal path stays unchanged.
**Blocked by:** PyQt GUI architecture decision (Phase 5).
**Added:** 2026-03-24 (from /plan-ceo-review, Week 6 terminal UI redesign)

---

### T-003 — Deduplicate DEVMODE struct + mode enumeration
**Priority:** P2
**Effort:** S human / S with CC
**Why:** `display_setter.py` and `monitor_dumper.py` each define a `DEVMODE` ctypes struct and `_enum_all_modes()` logic independently. Risk of silent divergence if one copy is updated without the other.
**Fix:** Extract shared struct + enumeration helpers to `src/utils/display_utils.py`. Both files import from there.
**Blocked by:** Nothing.
**Added:** 2026-04-07 (from /plan-eng-review, Priority 2 deferred item)

---

### T-004 — Type PipelineContext.llm properly
**Priority:** P2
**Effort:** XS human / XS with CC
**Why:** `llm: object = None` in `base.py` defeats type checking. If the wrong object is passed, the error surfaces deep in `action_proposer.py` with no useful traceback. A Protocol or proper Optional type fixes this at zero runtime cost.
**Fix:** Define a `LLMProtocol` with `__call__` signature, or import `Optional[Llama]` under a `TYPE_CHECKING` guard in `base.py`.
**Blocked by:** Nothing.
**Added:** 2026-04-07 (from /plan-eng-review, Priority 2 deferred item)

---

### T-006 — Observability & Instrumentation
**Priority:** P3
**Effort:** L human / L with CC
**Why:** No phase timing snapshots, no per-check success/failure ratios, no metrics aggregation. Logs exist but no structured performance data. Value only materializes when the codebase grows significantly or multiple contributors are involved.
**Fix:** Optional metric collection via `@instrument` decorator or a metrics registry.
**Blocked by:** Nothing. Defer until codebase or team grows.
**Added:** 2026-04-11 (merged from todo.md Issue 3.3)

---

## Completed

### T-003 — Deduplicate DEVMODE struct + mode enumeration
**Completed**: 2026-04-08
`src/utils/display_utils.py` created with canonical `DEVMODE` struct and `enum_raw_modes()`. Both `monitor_dumper.py` and `display_setter.py` now import from there. Local definitions removed. 5 tests in `tests/test_display_utils.py`.

---

### T-004 — Type PipelineContext.llm properly
**Completed**: 2026-04-08
`llm: object = None` changed to `llm: Optional[Llama] = None` in `src/pipeline/base.py`. `Llama` added to `TYPE_CHECKING` import block alongside the other forward-reference types.

---

### T-002 — Harden LLM output printing against UnicodeEncodeError
**Completed**: 2026-04-11
`sys.stdout.reconfigure(errors="replace")` added early in `src/main.py` via `isinstance` check. Non-encodable characters now print as `?` instead of crashing. 1 new test in `tests/test_formatting.py`.

---

### T-005 — Phase execution status visible to orchestrator
**Completed**: 2026-04-11
`PhaseResult` dataclass added to `src/pipeline/base.py`; all 5 phase `run()` methods return it; orchestrator in `phases.py` captures and logs non-completed results via debug logger.
