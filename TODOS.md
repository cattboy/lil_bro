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

### T-006 — Observability & Instrumentation
**Priority:** P3
**Effort:** L human / L with CC
**Why:** No phase timing snapshots, no per-check success/failure ratios, no metrics aggregation. Logs exist but no structured performance data. Value only materializes when the codebase grows significantly or multiple contributors are involved.
**Fix:** Optional metric collection via `@instrument` decorator or a metrics registry.
**Blocked by:** Nothing. Defer until codebase or team grows.
**Added:** 2026-04-11 (merged from todo.md Issue 3.3)

---

### T-007 — Multi-arch PawnIO extraction + build.py arch flag
**Priority:** P3
**Effort:** M human / M with CC
**Why:** `PawnIO_setup.exe` is a multi-arch installer (x64 + ARM64 `.sys` files). Currently only the x64 variant is kept; the ARM64 file is discarded. An ARM64 lil_bro build would require re-running the full extractor for a file we already had.
**Fix:** Update `tools/PawnIO_Latest_Check/update_pawnio.ps1` to copy each arch variant into `resources/extracted/<arch>/PawnIO.sys`; add `--arch` flag to `build.py` that selects the correct variant before the lhm-server build step. Step 0 guard must validate both arch subfolders before short-circuiting. Add `/tools/PawnIO_Latest_Check/resources/extracted/` to `.gitignore`.
**Acceptance:** `python build.py` unchanged (x64 default); `python build.py --arch arm64` embeds ARM64 driver; re-run with both subfolders present is a no-op.
**Blocked by:** Nothing. Target post pawnio-cleanup sprint.
**Added:** 2026-04-19 (consolidated from docs/todos.md)

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
