# Refactor report: src/utils/formatting.py

## Outcome
- Before: 387 lines
- After (target file): 343 lines (−44, −11%)
- New module: `src/utils/_console.py` (62 lines, holds `resize_console_window` + docstring guardrails)
- Net code change: +18 lines from the new module's docstring + guardrail comments
- `lil_bro.spec` `hiddenimports` updated: `src.utils._console` added explicitly

## Chunks completed
| # | Description                          | Commit  | LOC moved |
|---|--------------------------------------|---------|-----------|
| 1 | Extract `_console.py`                | 9fe4438 | ~45       |

## Test suite
- Target tests: `tests/test_formatting.py` + `tests/test_revert_routing.py` — 38 pass before, 38 pass after.
- New tests added: 0.

## Why only one chunk
The investigation flagged four candidate seams. Three of them — handler registry, prompts, print helpers — are blocked by the **test direct-attribute-access pattern**: `conftest.py` writes `formatting._APPROVAL_HANDLER = X` directly (not via setters), and three other test files read `formatting._DEFAULT_SINK` / `_APPROVAL_HANDLER` / `_CONFIRM_HANDLER` / `_BENCHMARK_SCORE_SINK` directly. Splitting any of those into a sibling module would create a dual-binding (the conftest write mutates only the re-export; consumers in the new home read their own module's binding). The fix exists (rewrite 4 test files + conftest to use setters/getters, or install `__getattr__`/`__setattr__` proxies) but the cost outweighs the ~130-LOC win for a subsystem that is already conceptually one piece (the late-lookup contract is documented architecture).

`resize_console_window` is the one truly isolated seam — no coupling to the handler registry, sinks, or print helpers. Extracting it is a Pattern 2 (Split IO from Logic) win even at modest LOC.

## Devil's advocate concerns addressed
- **Concern 1 — test selector:** Replaced `-k formatting or test_main` (which excluded `test_revert_routing.py`) with explicit file list.
- **Concern 2 — function-local imports:** Preserved verbatim in `_console.py`; added a guardrail note in the module docstring.
- **Concern 3 — PyInstaller hiddenimports:** Added `'src.utils._console'` to `lil_bro.spec` per the spec's explicit-listing convention.
- **Concern 4 — Serena hygiene ordering:** Added import BEFORE removing the symbol so `formatting.py` was never in a momentarily broken intermediate state.
- **Concern 5 — rationale framing:** Reframed conservatism around the test-direct-attribute pattern (the real blocker) rather than circular imports (a secondary issue).

## Deferred follow-ups
- **Handler-registry split (130 LOC potential win):** Blocked by direct-attribute-access in 4 test files. A future PR could: (a) rewrite tests to use setters/getters, then (b) extract `_handlers.py`. Net gain meaningful only with both steps.
- **`formatting.py` still at 343 lines** — 43 over the 300 threshold. Not addressed by this refactor; the bulk is the unsplittable late-lookup subsystem.
- **`_ASCII_FALLBACK` reload-based tests** — currently use `importlib.reload(formatting)`. If the constant ever moves, the reload target must move too.

## PyInstaller note
`src.utils._console` explicitly added to `lil_bro.spec` `hiddenimports` (line 98 in the spec, after the existing `src.agent_tools` entries). Static analyzer would likely have caught the `from ._console import` line anyway, but the spec's pattern is "list, not trust."
