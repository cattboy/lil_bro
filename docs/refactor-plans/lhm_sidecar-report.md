# Refactor report: src/collectors/sub/lhm_sidecar.py

## Outcome
- Before: 421 lines
- After (target file): 348 lines (−73, −17%)
- New modules (all in `src/collectors/sub/`):
  - `lhm_discovery.py` — 52 lines (executable discovery + search paths)
  - `lhm_http.py` — 31 lines (HTTP constants + readiness probe)
  - `lhm_process_utils.py` — 41 lines (port/PID introspection)
- Net code change: +51 lines across 4 files (separation overhead from docstrings + `__all__` + import blocks)

## Chunks completed
| # | Description                            | Commit  | LOC moved |
|---|----------------------------------------|---------|-----------|
| 1 | Extract `lhm_discovery.py`             | 3c0abc4 | ~30       |
| 2 | Extract `lhm_http.py`                  | 02263e7 | ~20       |
| 3 | Extract `lhm_process_utils.py`         | 5453cb8 | ~30       |

## Test suite
- Target tests: `tests/test_lhm_sidecar.py` — 23 pass before, 23 pass after.
- Test edits required: 5 `@patch` decorator retargets (3 in chunk 1, 2 each in chunks 2 and 3). All other patches kept on `lhm_sidecar` to preserve the dual-binding mock surface.
- New tests added: 0.

## Devil's advocate concerns addressed
- **Concern 1 — `urlopen` patches at lines 293/307:** Explicitly preserved on `lhm_sidecar` — they target `fetch_data` (still on the class).
- **Concern 2 — import form:** All three new imports use `from .lhm_X import name`, putting the names into `lhm_sidecar`'s module globals so `@patch("...lhm_sidecar.<name>")` and bare-name lookups in `LHMSidecar` methods both work.
- **Concern 3 — dual-binding contract:** Documented in plan; `__all__` added to each new module.
- **Concern 4 — `_POLL_INTERVAL` / `_STARTUP_TIMEOUT`:** Covered by the unified contract.
- **Concern 5 — inventory math:** Corrected to 9 class members.
- **Concern 6 — new-file imports:** Each new module declares its own `Optional`, `os`, `sys`, `json`, `urllib`, `socket`, `subprocess` as needed.
- **Concern 7 — PyInstaller:** Static `from .X import Y` lines are traceable by PyInstaller's analyzer. Flagged as a post-merge smoke-test item.

## Deferred follow-ups
- **`LHMSidecar` class itself stays at ~290 lines.** `_request_graceful_shutdown` (untested directly) and `start` (multi-branch elevation/wait state machine) remain the biggest internal methods. A future refactor could lift the process-launch elevation block into `lhm_process_utils.py`, but it accesses instance state (`self._process`, `self._elevated`) so it would need a different shape — out of scope for this v1.
- **Pyright "not accessed" / "import could not be resolved"** warnings for the re-exports are expected. The "could not be resolved" is Pyright's static analyzer lagging; the imports work at runtime (tests pass).
- **PyInstaller smoke test:** verify `LHMSidecar.start()` works in a freshly-built `lil_bro.exe`. Static analysis should pick up the new modules but worth confirming before the next release.

## PyInstaller note
No new modules under `src/gui/widgets/`. New modules under `src/collectors/sub/` are imported via direct `from .X import Y` lines that PyInstaller's static analyzer should pick up automatically — but flagged as a smoke-test follow-up.
