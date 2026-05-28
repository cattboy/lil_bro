# Refactor plan: src/utils/formatting.py

## Current shape
- Line count: 387
- 30 external importers (heaviest imported module in the codebase after `print`/stdlib)
- 5 test files; conftest.py autouse fixture snapshots/restores `_DEFAULT_SINK`, `_APPROVAL_HANDLER`, `_CONFIRM_HANDLER`; test_gui_bridge.py directly reads `formatting._DEFAULT_SINK`/`_APPROVAL_HANDLER`/`_CONFIRM_HANDLER`/`_BENCHMARK_SCORE_SINK` as module attributes; test_formatting.py uses `importlib.reload(formatting)` to re-trigger `_ASCII_FALLBACK` detection.

## Why this refactor is conservative
The investigation flagged four candidate seams (handler registry, prompts, print helpers, console resize). The one load-bearing blocker against extracting any of the first three is the **test direct-attribute-access pattern**:

- `tests/conftest.py:41-45` does `formatting._APPROVAL_HANDLER = snapshot[1]` (direct attribute writes, not setter calls) to restore handler state between tests.
- `tests/test_gui_bridge.py:18-21` and `tests/test_cli_unchanged.py:50-52` directly read `formatting._DEFAULT_SINK`, `_APPROVAL_HANDLER`, `_CONFIRM_HANDLER`, `_BENCHMARK_SCORE_SINK` as module attributes.

Moving any handler state to a sibling and re-exporting it creates a **dual-binding problem**: the conftest write would mutate only `formatting`'s re-export binding, while consumers in the new home read their own module's binding. The fix exists (rewrite the 4 test files to use setter/getter API, or install module-level `__getattr__`/`__setattr__` proxies on `formatting`), but it's a non-trivial tax for a 130-LOC win on code that is already conceptually a single subsystem (the late-lookup pattern is documented architecture, not accidental complexity).

The print helpers could in theory split with bottom-of-file imports in `formatting.py` to break the import cycle, but the win there is also modest and the print helpers share `_emit` which itself reads `_DEFAULT_SINK` — same dual-binding hazard for that one symbol if `_emit` moves too.

The one clean seam is `resize_console_window` — fully isolated ctypes IO, no coupling to the handler registry or print sinks. Extracting it is a Pattern 2 (Split IO from Logic) win even if it only buys ~45 lines.

## Target shape
- `src/utils/_console.py` — NEW. Holds `resize_console_window()` only.
- `formatting.py` after refactor: ~345 lines (down from 387). Keeps everything else.

## Chunks

### Chunk 1: Extract `_console.py`
- **Symbols moved:** `resize_console_window()` (~45 lines including docstring + try/except)
- **New file:** `src/utils/_console.py`
- **Imports updated in formatting.py:** add `from ._console import resize_console_window`
- **External callers:** `src/main.py` imports `resize_console_window` from `formatting`; `tests/test_revert_routing.py::test_revert_flag_routes_to_revert_phase` patches `src.main.resize_console_window`. Both preserved via re-export (the patch target `src.main.resize_console_window` stays valid because `src/main.py` still does `from src.utils.formatting import resize_console_window`, binding the name on `src.main`).
- **Test impact:** `tests/test_formatting.py` has 8 tests touching `resize_console_window` (happy path + Win32 mock + WT_SESSION skip + ShellExecuteW return-value checks). They patch `ctypes.windll` at the real `ctypes` module path, not `formatting.ctypes` — works regardless of which module the function lives in **because the function does `import ctypes` inside its body** (function-local imports are load-bearing for these test patches). No test edits required.
- **Tests after:** `pytest tests/test_formatting.py tests/test_revert_routing.py --tb=short -q`
- **Serena hygiene (corrected order — add import BEFORE removing symbol so formatting.py is never momentarily broken):**
  1. `Write` `src/utils/_console.py` (new file — allowed via Write per the hook's new-path carve-out)
  2. `restart_language_server`
  3. Built-in `Edit` to add `from ._console import resize_console_window` near top of `formatting.py` (module-level import — hook-allowed)
  4. `restart_language_server`
  5. Serena `safe_delete_symbol` on `resize_console_window` in `formatting.py` (or AST-based Bash removal if it refuses)
  6. `Read` to verify no orphan blank lines per the `safe_delete_orphans` memory; clean with `Edit` if found
  7. `restart_language_server`
  8. Run target tests
- **PyInstaller:** Add `'src.utils._console'` to `hiddenimports` in `lil_bro.spec` per the codebase's explicit-listing convention. The static `from ._console import` in `formatting.py` should be picked up automatically, but the spec's pattern is to list, not trust.
- **Guardrail for `_console.py`:** preserve function-local `import ctypes` / `import os` inside `resize_console_window`. Tests at `tests/test_formatting.py:296,318,328,339,353,369,384,403` patch `ctypes.windll` directly — function-local imports keep that patch target effective. Hoisting the imports to module top would still work for `ctypes.windll`, but if a future cleanup switches to `from ctypes import windll`, the patches break silently. Note this in a one-line comment.

## Devil's advocate concerns
- **Concern 1 (Test gaps):** Original "tests after" selector missed `test_revert_routing.py`. **Resolution:** Replaced with explicit file list.
- **Concern 2 (Behavior-change):** Function-local imports in `resize_console_window` are load-bearing for test patches at `ctypes.windll`. **Resolution:** Guardrail note added; preserve function-local imports.
- **Concern 3 (PyInstaller):** Spec's convention is explicit listing. **Resolution:** Plan now adds `'src.utils._console'` to `lil_bro.spec` hiddenimports.
- **Concern 4 (Serena hygiene):** Original ordering removed symbol before adding import — broken intermediate state. **Resolution:** Reordered to "Write new → restart → add import in formatting.py → restart → remove symbol from formatting.py → verify no orphans → restart".
- **Concern 5 (Rationale framing):** "Circular import" was the wrong label for the print-helpers blocker. **Resolution:** Reframed the conservatism argument around the test-direct-attribute-access pattern (the real blocker), with circular-import mentioned only as a secondary concern.

## Untested risk
`resize_console_window` has strong test coverage (8 tests). The move is verbatim — no body change.

## Status
- [x] Phase 4 devil's advocate complete (5 concerns addressed)
- [x] User approved (auto mode)
- [x] Implementation complete (1 chunk committed)
- [x] All target tests passing (38/38)
