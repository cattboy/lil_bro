# QA Report — lil_bro CLI

**Date:** 2026-03-25
**Branch:** feat/week6-terminal-ui
**Mode:** Diff-aware (CLI project — no browser)
**Scope:** main.py module split (src/pipeline/ package, 8 new files) + terminal UI changes
**Base branch:** main
**Duration:** ~5 min

---

## Summary

| Metric | Value |
|--------|-------|
| Tests run | 246 (was 242) |
| Tests passing | 246 / 246 |
| Issues found | 2 |
| Issues fixed | 2 |
| Issues deferred | 0 |
| Health score | **97 → 98** |
| PR summary | QA found 2 issues, fixed 2, health score 97 → 98 |

---

## Issues Found & Fixed

### ISSUE-001 [LOW] — Incorrect type annotation in FIX_REGISTRY

**File:** `src/pipeline/fix_dispatch.py`
**Description:** `FIX_REGISTRY: dict[str, callable]` used the built-in `callable()` function as a type annotation. This is a type annotation correctness issue — `callable` is a runtime function, not a type. Static type checkers (mypy, pyright) would misinterpret this.
**Fix:** Added `from collections.abc import Callable`; changed to `dict[str, Callable[[dict], bool]]`
**Fix Status:** verified
**Commit:** `8e18793`

---

### ISSUE-002 [MEDIUM] — Missing test coverage for `_fix_power_plan` handler

**File:** `tests/test_fix_dispatch.py`
**Description:** All 4 auto-fixable handlers are registered in `FIX_REGISTRY`, but `_fix_power_plan` had zero test coverage. This is the most complex handler (4 lazy imports, 3 code paths: GUID match, name match, create new plan).
**Fix:** Added `TestFixPowerPlan` class with 4 tests covering:
- `test_power_plan_success_via_perf_guid` — happy path with matching PERF_GUID
- `test_power_plan_success_via_name_match` — fallback to name-based match
- `test_power_plan_creates_new_when_none_found` — creates plan when no match
- `test_power_plan_failure` — exception from `list_available_plans` returns False
**Fix Status:** verified
**Commit:** `4bb7ef9`

---

## Pre-existing Issues (Not From This Branch)

### WARNING — `test_thermal_monitor.py::test_monitor_captures_peak`

A background polling thread raises `StopIteration` when the mock's `side_effect` iterator is exhausted before the thread stops. This warning was present before this branch's changes — `tests/test_thermal_monitor.py` was not modified on this branch. Not blocking, but the test could be made more robust by fixing the mock setup.

---

## Health Score Breakdown

| Category | Score | Notes |
|----------|-------|-------|
| Functional | 100 | 246/246 tests pass, all imports clean |
| Code quality | 95 | ISSUE-001 fixed (type annotation), no runtime errors |
| Test coverage | 97 | ISSUE-002 fixed (power_plan handler now covered); 246 tests |
| Architecture | 100 | Clean import graph, no circular deps, correct state pattern |

**Final: 98/100**

---

## Commits Added by /qa

```
8e18793 fix(qa): ISSUE-001 -- use Callable[[dict], bool] instead of callable builtin
4bb7ef9 test(qa): ISSUE-002 -- regression tests for _fix_power_plan handler
```
