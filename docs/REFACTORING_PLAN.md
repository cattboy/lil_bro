# lil_bro Refactoring Plan — Remaining Work

**Branch**: `refactor/priority-1-improvements`
**Plan started**: 2026-04-07 | **Trimmed**: 2026-04-11
**Full history**: `docs/DONE.md`

---

## Status

**All refactoring work is complete.** Test count: 409 passing.

See `docs/DONE.md` for the full history of completed work. Deferred future-work items (T-001, 3.3) are tracked in `todo.md` (project root).

---

## Explicitly Out of Scope

Decided during eng-review and Priority 2-B analysis. Do not reopen without a strong new reason.

| Issue | Decision |
|-------|----------|
| **Setter interface Protocol** (2.5) | `display_setter.py`'s `(bool, str)` tuple return is intentional — the dry_run/apply two-phase pattern requires it. Not changing. |
| **Phase Dependency Framework** (PhaseContract classes) | Over-engineered for a 4,000-line solo tool. The null guard in `phase_final.py` is sufficient. |
| **CollectorResult generic type** | Deferred — codebase not grown enough to justify. |
| **FallbackStrategy Protocol** (3.1) | The four fallback paths have different triggers, return types, and caller patterns. A unified abstraction would add indirection without reducing complexity. Closed. |

---

*For completed work see `docs/DONE.md`.*
