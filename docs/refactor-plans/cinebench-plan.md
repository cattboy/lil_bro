# Refactor plan: src/benchmarks/cinebench.py

## Current shape
- Line count: 491
- Top-level symbols: 1 class (4 methods), 4 module-level functions, 5 constants, 1 logger
- Top 3 coupling concerns from architecture-mapper:
  1. `phase_baseline.py` instantiates `BenchmarkRunner()` and calls `run_benchmark()` — hard dependency on the public surface
  2. `phase_final.py` reads `ctx.runner.has_cinebench` — public attribute coupling
  3. `src/config.py` `BenchmarkConfig.cinebench_timeout` is read at module import; the test suite imports `_CINEBENCH_SEARCH_PATHS`, `SW_HIDE`, `SW_MINIMIZE`, `_minimize_cinebench_window` as private names

## Target shape
Proposed new modules (sibling files under `src/benchmarks/`):

- `src/benchmarks/cinebench_discovery.py` — Cinebench executable discovery. Holds `_REPO_ROOT`, `_CINEBENCH_SEARCH_PATHS`, `find_cinebench()`.
- `src/benchmarks/cinebench_monitor.py` — User-facing threading helpers during a benchmark run. Holds `SW_HIDE`, `SW_MINIMIZE`, `_keyboard_abort_watcher()`, `_benchmark_progress_printer()`, `_minimize_cinebench_window()`.
- `src/benchmarks/cinebench_parser.py` — Pure regex-based score extraction. Holds the `_parse_output` logic as a module-level function (the method delegates to it).

`cinebench.py` after refactor: ~300 lines (down from 491). Keeps `BenchmarkRunner` (with `__init__`, `run_benchmark`, `_run_cinebench` orchestration, `_parse_output` shim) plus re-export shims for symbols the test suite reaches into by private name. `_run_cinebench` (190 LOC) itself stays — it's the hotspot but is out of scope for this refactor.

### Protected test-import surface (must stay re-exported from cinebench.py)
The test suite reaches into private names. After refactor, `cinebench.py` must still expose these via `from .X import Y`:
- `BenchmarkRunner`, `find_cinebench`, `_CINEBENCH_SEARCH_PATHS` (top-level imports in test file)
- `_state` (imported by abort/cancel tests — already a re-export from `..pipeline`, stays)
- `SW_HIDE`, `SW_MINIMIZE`, `_minimize_cinebench_window`, `_keyboard_abort_watcher`, `_benchmark_progress_printer` (used via `@patch("src.benchmarks.cinebench.<name>")`)
- `prompt_approval`, `print_warning`, `print_info`, `notify_benchmark_started` (already imported here, patched by tests)

Re-export shims are **read-only**: a future test that wants to monkeypatch `cinebench._CINEBENCH_SEARCH_PATHS` will only mutate the cinebench-module binding, not the discovery-module binding `find_cinebench` actually reads. Document this in the new modules' docstrings.

Pattern(s) applied (from references/decomposition-patterns.md):
- **Pattern 1: Extract Module** — three cohesive seams identified by symbol-mapper
- **Pattern 2: Split IO from Logic** — parser is pure; discovery is mostly pure (file existence checks); monitor is IO
- Re-export shim approach (keeps the test suite's existing imports working)

## Chunks
Each chunk is one atomic commit. Tests must pass between chunks.

### Chunk 1: Extract `cinebench_discovery.py` (lowest risk first)
- **Symbols moved:** `_REPO_ROOT`, `_CINEBENCH_SEARCH_PATHS`, `find_cinebench()`
- **New files created:** `src/benchmarks/cinebench_discovery.py`
- **Imports updated in cinebench.py:** add `from .cinebench_discovery import _REPO_ROOT, _CINEBENCH_SEARCH_PATHS, find_cinebench`
- **Test edits required (devil's advocate Concern 1):** `find_cinebench`'s body uses `os.path.isfile`, which resolves against the new module's `os` binding after the move. Update three patch targets in `tests/test_benchmark_runner.py`:
  - line 13: `@patch("src.benchmarks.cinebench.os.path.isfile")` → `@patch("src.benchmarks.cinebench_discovery.os.path.isfile")`
  - line 22: same swap
  - line 28: same swap

  `BenchmarkRunner.__init__` keeps calling `os.path.isfile(cinebench_path)` itself, so the test at line 62 (`test_runner_explicit_path`) stays on the `cinebench` patch path — do NOT change that one.
- **Tests that should pass after:** `pytest -k benchmark_runner`
- **Serena hygiene:** Pattern D (new file via `Write`) — restart LS. Then Pattern B on cinebench.py (`Edit` to remove moved lines and add the re-export). Restart LS again after.

### Chunk 2: Extract `cinebench_parser.py`
- **Symbols moved:** logic of `BenchmarkRunner._parse_output` → module function `parse_output(text)`
- **New files created:** `src/benchmarks/cinebench_parser.py`
- **Imports updated in cinebench.py:** add `from .cinebench_parser import parse_output`. Convert `_parse_output` method body to `return parse_output(text)`.
- **External call sites:** none — `_parse_output` is only called via `self._parse_output(...)` inside `_run_cinebench`
- **Tests that should pass after:** `pytest -k benchmark_runner` (tests `test_parse_output_multi`, `test_parse_output_single`, `test_parse_output_empty` call `runner._parse_output(...)` — still works via the method shim)
- **Serena hygiene:** Pattern D (new file) + Pattern B on cinebench.py (Serena `replace_symbol_body` for `_parse_output`, then built-in `Edit` for import). Restart LS after.

### Chunk 3: Extract `cinebench_monitor.py`
- **Symbols moved:** `SW_HIDE`, `SW_MINIMIZE`, `_keyboard_abort_watcher`, `_benchmark_progress_printer`, `_minimize_cinebench_window`
- **New files created:** `src/benchmarks/cinebench_monitor.py`
- **Imports updated in cinebench.py:** add `from .cinebench_monitor import SW_HIDE, SW_MINIMIZE, _keyboard_abort_watcher, _benchmark_progress_printer, _minimize_cinebench_window`
- **Guardrail (devil's advocate Concern 4):** inside `_run_cinebench`, references to these symbols must remain bare names (e.g. `_keyboard_abort_watcher(...)`, not `cinebench_monitor._keyboard_abort_watcher(...)`). The test suite at line 251 does `@patch("src.benchmarks.cinebench._keyboard_abort_watcher")` — bare-name lookups in `_run_cinebench`'s scope honor that patch; qualified lookups would not.
- **External call sites:** test suite imports `_minimize_cinebench_window`, `SW_HIDE`, `SW_MINIMIZE` from `src.benchmarks.cinebench` — preserved via re-export. Patch decorators target `src.benchmarks.cinebench._keyboard_abort_watcher` etc., which still resolves via re-export.
- **Tests that should pass after:** `pytest -k benchmark_runner` — particularly the window-classification tests, SW_HIDE/SW_MINIMIZE constant tests, and the timeout/abort tests that patch the helpers.
- **Serena hygiene (devil's advocate Concern 5):** Chunk 3 mixes Serena deletions of 3 module-level functions with built-in `Edit` deletions of 2 constants and an import. Order:
  1. Pattern D: `Write` the new `cinebench_monitor.py` first
  2. `restart_language_server`
  3. Serena `safe_delete_symbol` for `_keyboard_abort_watcher`, `_benchmark_progress_printer`, `_minimize_cinebench_window` (verify each for orphan whitespace lines per the `safe_delete_orphans` memory; clean with built-in `Edit` if found)
  4. `restart_language_server` (Serena deletes count as Serena edits but `safe_delete_symbol` may leave non-symbol residue we cleaned with `Edit` — over-restart is cheap)
  5. Built-in `Edit` to remove the `SW_HIDE`/`SW_MINIMIZE` constant lines and add the new `from .cinebench_monitor import ...` line
  6. `restart_language_server` again before the next phase

## Untested risk
From test-coverage-mapper: thinly-covered symbols this plan moves:
- `_benchmark_progress_printer` → moves to `cinebench_monitor.py`. Untested directly; behavior is just `time.sleep` + print. Refactor preserves the function verbatim — copy-paste move, no behavior change.
- `_keyboard_abort_watcher` → moves to `cinebench_monitor.py`. Mocked in abort tests but never run live. Same: verbatim move.

Mitigation: Each chunk is a verbatim symbol move + re-export shim. Behavior change risk is near-zero.

## Devil's advocate concerns

- **Concern 1 (Hidden coupling / Behavior-change):** `find_cinebench` test patches target `src.benchmarks.cinebench.os.path.isfile`, which becomes a dead patch once the body moves. **Resolution:** Chunk 1 now mandates swapping the three patch decorators to `src.benchmarks.cinebench_discovery.os.path.isfile` in the same commit. The explicit-path test stays on the cinebench module path (its `os` reference comes from `__init__`, which stays).
- **Concern 2 (Hidden coupling, awareness):** Re-export shims for module-level constants are read-only — monkeypatching `cinebench._CINEBENCH_SEARCH_PATHS` would not affect `find_cinebench`'s iteration. **Resolution:** Documented in the new modules' docstrings; no test today exercises this, so no code change needed.
- **Concern 3 (Plan completeness):** `_state` import was missing from the protected re-export inventory. **Resolution:** Added `_state` (and the other patched names) to the protected-surface section above the chunks.
- **Concern 4 (Hidden coupling):** `_run_cinebench` must keep referencing the helpers by bare name so `@patch` decorators on the `cinebench` module hit them. **Resolution:** Pinned as a guardrail in Chunk 3; do not "clean up" to qualified `cinebench_monitor.X(...)` references.
- **Concern 5 (Serena LS desync):** Chunk 3 mixes Serena `safe_delete_symbol` with built-in `Edit` for constants/imports. A single end-of-chunk restart is too coarse. **Resolution:** Chunk 3 hygiene now specifies a 6-step ordered sequence with intermediate `restart_language_server` calls.

Considerations acknowledged (not blocking, not separately tracked):
- Plan's line-count target revised from "~150" to "~300" after refactor (the devil's-advocate arithmetic was right; the symbol-mapper's pre-refactor count of 408 lines was also off vs. the discovery script's 491).
- `_run_cinebench` (190 LOC) remains the dominant chunk after this refactor. Out of scope for v1.

## Status
- [x] Phase 4 devil's advocate complete (all 5 concerns addressed in plan)
- [ ] User approved
- [ ] Implementation complete
- [ ] All tests passing
