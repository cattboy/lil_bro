# Refactor report: src/benchmarks/cinebench.py

## Outcome
- Before: 491 lines
- After (target file): 294 lines (−197, −40%)
- New modules:
  - `src/benchmarks/cinebench_discovery.py` — 48 lines (executable discovery)
  - `src/benchmarks/cinebench_parser.py` — 45 lines (pure score-log parser)
  - `src/benchmarks/cinebench_monitor.py` — 145 lines (keyboard/progress/window threads)
- Net code change: +41 lines across 4 files (separation overhead from new docstrings + import lines)

## Chunks completed
| # | Description                                  | Commit  | LOC moved |
|---|----------------------------------------------|---------|-----------|
| 1 | Extract `cinebench_discovery.py`             | 9b265a2 | ~38       |
| 2 | Extract `cinebench_parser.py`                | 6e2ac7e | ~37       |
| 3 | Extract `cinebench_monitor.py`               | 23f81d1 | ~120      |

## Test suite
- Target tests: `tests/test_benchmark_runner.py` — 24 pass before, 24 pass after.
- Full repo suite: pre-existing failure in `tests/test_temp_audit.py::test_analyze_temp_folders_under_threshold` (verified failing on the pre-refactor commit too — unrelated to this refactor).
- New tests added: 0 (refactor-only).

## Devil's advocate concerns addressed
- **Concern 1 — `find_cinebench` test patches:** Three `@patch("src.benchmarks.cinebench.os.path.isfile")` decorators retargeted to `cinebench_discovery.os.path.isfile` in the same Chunk 1 commit.
- **Concern 2 — re-export shim semantics:** Documented in new modules' docstrings; no live test depends on mutation.
- **Concern 3 — `_state` protected re-export:** Inventoried in plan; `_state` stays imported in `cinebench.py` and is still reachable as `cinebench._state` for the abort/cancel tests.
- **Concern 4 — bare-name references in `_run_cinebench`:** Preserved. The simplifier critic was explicitly told not to qualify them, and verification confirms `_keyboard_abort_watcher`/`_benchmark_progress_printer`/`_minimize_cinebench_window` remain bare-name calls inside the method body.
- **Concern 5 — Serena LS desync during Chunk 3:** `safe_delete_symbol` refused (false-positive refs via the new import); replaced with an AST-based Python rewrite via Bash for the function removals, followed by a built-in `Edit` for the import block, with `restart_language_server` between phases.

## Deferred follow-ups
- **`BenchmarkRunner._run_cinebench` (190 LOC) is still the hotspot.** This refactor explicitly scoped it out. Future refactor could lift the per-thread orchestration into a small context manager, but it would touch the human-in-the-loop subprocess flow and warrants its own plan.
- **Pyright "not accessed" warnings** for `_REPO_ROOT`, `_CINEBENCH_SEARCH_PATHS`, `SW_MINIMIZE`, `Path` in cinebench.py are expected — these are protected re-exports the test suite reaches into. Add `# noqa` or a `__all__` if Pyright noise becomes annoying.
- **`tests/test_temp_audit.py::test_analyze_temp_folders_under_threshold`** is pre-existing red; surface separately.

## PyInstaller note
No new modules landed under `src/gui/widgets/`. PyInstaller's static analyzer traces sibling-package `from .cinebench_discovery import ...` lines fine. No `hiddenimports` update needed.
