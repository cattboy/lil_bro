# Refactor plan: src/collectors/sub/lhm_sidecar.py

## Current shape
- Line count: 421
- Top-level symbols: 1 class `LHMSidecar` (9 members: `__init__`, `is_running` property, `start`, `_drain_stderr`, `_drain_stdout`, `stop`, `_request_graceful_shutdown`, `_kill_process`, `fetch_data`), 4 module-level functions (`_find_elevated_pid`, `_is_port_in_use`, `_is_lhm_responding`, `find_lhm_executable`), constants (`LHM_PORT`, `LHM_URL`, `_STARTUP_TIMEOUT`, `_POLL_INTERVAL`, `_PROJECT_ROOT`, `_LHM_SEARCH_PATHS`)
- 9 external importers (pipeline + GUI startup), 1 test file (`tests/test_lhm_sidecar.py`) with comprehensive patching of `socket`, `urllib`, `os.path.isfile`, `subprocess.Popen`, `subprocess.run`

## Target shape
- `src/collectors/sub/lhm_discovery.py` — Executable discovery. Holds `_PROJECT_ROOT`, `_LHM_SEARCH_PATHS`, `find_lhm_executable()`.
- `src/collectors/sub/lhm_http.py` — HTTP endpoint constants + readiness probe. Holds `LHM_PORT`, `LHM_URL`, `_STARTUP_TIMEOUT`, `_POLL_INTERVAL`, `_is_lhm_responding()`.
- `src/collectors/sub/lhm_process_utils.py` — Process introspection helpers. Holds `_is_port_in_use()`, `_find_elevated_pid()`.

`lhm_sidecar.py` after refactor: ~290 lines (down from 421). Keeps `LHMSidecar` class (`start`, `stop`, `_request_graceful_shutdown`, `_kill_process`, `_drain_stdout`, `_drain_stderr`, `fetch_data`, `is_running`, `__init__`) + re-export shims.

Pattern(s) applied:
- **Pattern 1: Extract Module** for three cohesive seams
- **Pattern 2: Split IO from Logic** (discovery is mostly pure file-existence; HTTP is its own thin IO layer; process utils are OS subprocess/socket IO)
- The LHMSidecar class itself stays — it's stateful and coordinates the helpers; decomposing it would be a Pattern 4 god-class split that this v1 refactor scopes out.

### Protected test-import surface (must stay re-exported from lhm_sidecar.py)
- `LHMSidecar` (imported by 7 src modules)
- `LHM_URL` (imported by `benchmarks/thermal_monitor.py`, `collectors/sub/libra_hm_dumper.py`)
- `LHM_PORT`, `find_lhm_executable`, `_is_port_in_use`, `_is_lhm_responding` (imported by test file)

Tests heavily patch `src.collectors.sub.lhm_sidecar.<stdlib_module>.<attr>` — same hazard as the cinebench refactor. Each chunk must retarget the affected patch decorators.

### Dual-binding contract (applies to all moved free functions + constants)
After a chunk lands, a moved symbol exists in TWO modules: the new home (real definition) and `lhm_sidecar` (re-exported binding). `@patch("src.collectors.sub.lhm_sidecar.X")` only replaces the `lhm_sidecar` binding. `LHMSidecar` methods call moved symbols by bare name (e.g. `_is_lhm_responding()` not `lhm_http._is_lhm_responding()`), and Python resolves bare names against the calling module's globals, so the patched `lhm_sidecar` binding is what gets called. Two rules follow:

1. **Import form MUST be `from .lhm_X import name` (not `from . import lhm_X`).** The `from … import` form binds the name into `lhm_sidecar`'s globals; the module-form would not, and existing `@patch("src.collectors.sub.lhm_sidecar.<name>")` decorators would no-op.
2. **External callers MUST import the public surface from `lhm_sidecar`, not from the new homes.** The new modules are implementation detail. Add `__all__` to each new module advertising the intent.

### Imports needed by each new module
- `lhm_discovery.py`: `import os`, `import sys`, `from typing import Optional`
- `lhm_http.py`: `import json`, `import urllib.request`
- `lhm_process_utils.py`: `import socket`, `import subprocess`, `from typing import Optional`

## Chunks

### Chunk 1: Extract `lhm_discovery.py` (lowest risk first; well-tested surface)
- **Symbols moved:** `_PROJECT_ROOT`, `_LHM_SEARCH_PATHS`, `find_lhm_executable()`
- **New file:** `src/collectors/sub/lhm_discovery.py`
- **Imports updated in lhm_sidecar.py:** add `from .lhm_discovery import _PROJECT_ROOT, _LHM_SEARCH_PATHS, find_lhm_executable`
- **Test edits required:** `find_lhm_executable`'s body uses `os.path.isfile`. Retarget three patch decorators in `tests/test_lhm_sidecar.py`:
  - lines 53, 63, 73: `@patch("src.collectors.sub.lhm_sidecar.os.path.isfile")` → `@patch("src.collectors.sub.lhm_discovery.os.path.isfile")`
- **Tests after:** `pytest -k lhm_sidecar`
- **Serena hygiene:** Pattern D (new file) → restart LS → Python-AST removal of `find_lhm_executable` + constants from lhm_sidecar.py (Serena `safe_delete_symbol` will refuse due to apparent refs — same workaround as cinebench chunk 1) → restart LS → built-in `Edit` for import line → restart LS.

### Chunk 2: Extract `lhm_http.py`
- **Symbols moved:** `LHM_PORT`, `LHM_URL`, `_STARTUP_TIMEOUT`, `_POLL_INTERVAL`, `_is_lhm_responding()`
- **New file:** `src/collectors/sub/lhm_http.py`
- **Imports updated in lhm_sidecar.py:** `from .lhm_http import LHM_PORT, LHM_URL, _STARTUP_TIMEOUT, _POLL_INTERVAL, _is_lhm_responding`
- **Test edits required:** `_is_lhm_responding`'s body uses `urllib.request.urlopen`. Retarget ONLY the two decorators that exercise `_is_lhm_responding`:
  - line 36: `@patch("src.collectors.sub.lhm_sidecar.urllib.request.urlopen")` → `@patch("src.collectors.sub.lhm_http.urllib.request.urlopen")`
  - line 46: same swap
  - **DO NOT touch lines 293, 307.** Those decorate `test_fetch_data_success` / `test_fetch_data_failure`, which exercise `LHMSidecar.fetch_data`. `fetch_data` stays on the class in `lhm_sidecar.py` and resolves `urllib` against `lhm_sidecar`'s top-level `import urllib.request`. Retargeting them would make the mock miss.
  - Tests patching `lhm_sidecar._is_lhm_responding` directly (lines 83, 93, 114, 142, 173, 268, 318, 347) stay as-is — they target the re-exported binding which `LHMSidecar.start()` and `is_running` look up via globals.
- **External callers:** `benchmarks/thermal_monitor.py` and `collectors/sub/libra_hm_dumper.py` import `LHM_URL` from `lhm_sidecar` — preserved via re-export.
- **Guardrail:** `LHMSidecar.is_running` and `LHMSidecar.start` call `_is_lhm_responding` by bare name. Keep bare. `LHMSidecar.fetch_data` references `LHM_URL` by bare name — keep bare.
- **Tests after:** `pytest -k lhm_sidecar`
- **Serena hygiene:** Pattern D + AST removal of the function + built-in `Edit` for constants/imports. Restart LS between each step.

### Chunk 3: Extract `lhm_process_utils.py`
- **Symbols moved:** `_is_port_in_use()`, `_find_elevated_pid()`
- **New file:** `src/collectors/sub/lhm_process_utils.py`
- **Imports updated in lhm_sidecar.py:** `from .lhm_process_utils import _is_port_in_use, _find_elevated_pid`
- **Test edits required:** `_is_port_in_use` body uses `socket.socket`. Retarget two decorators:
  - lines 16, 25: `@patch("src.collectors.sub.lhm_sidecar.socket.socket")` → `@patch("src.collectors.sub.lhm_process_utils.socket.socket")`
  - `_find_elevated_pid` is never patched directly (only mocked via `subprocess.run` inside `LHMSidecar` methods which stay) — no test edits for this one.
- **Guardrail:** `LHMSidecar.start` calls `_is_port_in_use` by bare name; `_request_graceful_shutdown` calls `_find_elevated_pid` by bare name. Keep bare.
- **Tests after:** `pytest -k lhm_sidecar`
- **Serena hygiene:** Pattern D + AST removal + built-in `Edit`. Restart LS between steps.

## Untested risk
From test-coverage-mapper:
- `_find_elevated_pid` (untested directly) — moves verbatim to `lhm_process_utils.py`. No body change.
- `LHMSidecar._request_graceful_shutdown` (untested directly) — stays in `lhm_sidecar.py`. No change.

Mitigation: every chunk is a verbatim symbol move + re-export shim + test-patch retargeting. Behavior-change risk near zero.

## Devil's advocate concerns

- **Concern 1 (Test gaps):** Chunk 2 must explicitly NOT retarget `urlopen` patches at lines 293/307 — those exercise `fetch_data` which stays in the class. **Resolution:** Chunk 2 now spells out which patches stay vs. move.
- **Concern 2 (Hidden coupling):** Import form must be `from .lhm_X import name` not `from . import lhm_X`. **Resolution:** Dual-binding contract section added at top with the explicit rule.
- **Concern 3 (Future-proofing):** External callers must import from `lhm_sidecar`, not the new modules. **Resolution:** Documented; will add `__all__` to each new module.
- **Concern 4 (Behavior-change):** `_POLL_INTERVAL`/`_STARTUP_TIMEOUT` follow the same dual-binding rule. **Resolution:** Covered by the unified contract.
- **Concern 5 (Plan completeness):** Class member count was wrong (12 vs actual 9). **Resolution:** Corrected to 9 with names enumerated.
- **Concern 6 (Import cleanup):** New modules need their own `Optional`, `os`, `sys`, `json`, `urllib`, `socket`, `subprocess` imports. **Resolution:** Per-new-file import list added.
- **Concern 7 (PyInstaller):** Static analysis should resolve `from .X import Y` lines automatically. **Resolution:** Treat as awareness — verify by rebuilding the bundle and smoke-testing LHM start after the refactor lands. Out of scope for the test gate; flagged for post-merge.

## Status
- [x] Phase 4 devil's advocate complete (all 7 concerns addressed)
- [x] User approved (auto mode)
- [x] Implementation complete (3 chunks committed)
- [x] All target tests passing (23/23)
