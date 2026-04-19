# lil_bro — Outstanding Work Backlog v2

**Version:** 2.0  
**Date:** 2026-04-19  
**Purpose:** Sprint-backlog prompt for Opus. Use alongside `docs/DONE.md` (architecture, foundation, and P0 revert-feature detail).

> Completed items (T-002, T-003, T-004, T-005) are archived in `docs/DONE.md` v2.  
> Active in-progress work (revert feature, manifest-isolation merge) is detailed in `docs/DONE.md` § Active Work.

---

## Priority Scale

| Tier | Criteria | When to act |
|------|----------|-------------|
| **P0 — Finish now** | In-progress; half-built safety features erode trust | Before starting anything below |
| **P1 — Next sprint** | User-visible or build-critical; low regression risk | After P0 is merged and tested |
| **P2 — Schedule** | Meaningful quality win; no user impact until a later phase | When a sprint has capacity |
| **P3 — Defer** | Blocked, or ROI only materialises at scale | Revisit when prerequisite is met |

---

## P0 — Finish First: Revert Feature

**Branch:** `feature/revert-last-session`  
**Severity:** The session manifest is live and writing data on every run. Users cannot consume it. A safety feature with no UI is a liability.

Full implementation order, schema, UX mockups, and test requirements are in `docs/DONE.md` § P0 and `docs/completed/plan-revert-feature.md`. Do not start T-007 until this is merged and 441+ tests pass on `main`.

---

## P1 — T-007: Multi-arch PawnIO + `build.py --arch`

**Severity:** Additive — the x64 build path is completely unchanged. An ARM64 build currently requires re-running the full extractor for a `.sys` file that was already present in the installer and discarded.  
**Impact:** Enables zero-cost ARM64 builds once the flag exists.  
**Effort:** M | **Risk:** Low | **Blocked by:** Nothing

### What to change

**`tools/PawnIO_Latest_Check/update_pawnio.ps1`**
- Step 0 guard: require both `resources/extracted/x64/PawnIO.sys` (machine type `0x8664`) AND `resources/extracted/arm64/PawnIO.sys` (machine type `0xAA64`) to be present and correct before short-circuiting. If either is missing, run full extraction.
- Step 7 (after selecting x64 variant): also copy the arm64 variant to `resources/extracted/arm64/PawnIO.sys` and x64 to `resources/extracted/x64/PawnIO.sys`.
- Final copy to `tools/PawnIO/dist/PawnIO.sys` uses the `--arch` parameter (default: `x64`).

**`build.py`**
- Add `--arch` flag (`choices=["x64", "arm64"]`, `default="x64"`).
- Pre-build step (before lhm-server build): copy `resources/extracted/<arch>/PawnIO.sys` → `tools/PawnIO/dist/PawnIO.sys`.
- `run_pawnio_update()` passes `--arch` down so the ps1 knows which subfolder to validate or populate.
- `LhmServer.csproj` is unchanged — it always embeds from `tools/PawnIO/dist/PawnIO.sys`.

**`.gitignore`**
- Add `/tools/PawnIO_Latest_Check/resources/extracted/`

### Acceptance criteria
- `python build.py` (no flags) behaves identically to today — x64 driver.
- `python build.py --arch arm64` embeds the ARM64 driver in `lhm-server.exe`.
- Re-running when both arch subfolders already have correct machine types is a no-op (Step 0 exits early).
- Existing tests continue to pass; new tests cover `--arch` flag routing in `build.py` and dual-subfolder copy logic in the ps1.

---

## P2 — T-001: Future-proof `formatting.py` for GUI backend

**Severity:** Zero — the terminal path works correctly today.  
**Impact:** High when the GUI phase arrives; low until then.  
**Effort:** L | **Risk:** Low | **Blocked by:** PyQt GUI architecture decision (Phase 5 — not yet scoped)

### What to change

Add `return_str: bool = False` to every `print_*` function in `src/utils/formatting.py`. When `True`, return the formatted string instead of printing. The terminal call path is unchanged (default `False`). The future GUI backend calls with `return_str=True` and pipes the string to a widget.

```python
# Before
def print_success(msg: str) -> None:
    icon = "OK" if _ASCII_FALLBACK else "✓"
    print(f"{GREEN}{icon} {msg}{RESET}")

# After
def print_success(msg: str, return_str: bool = False) -> str | None:
    icon = "OK" if _ASCII_FALLBACK else "✓"
    out = f"{GREEN}{icon} {msg}{RESET}"
    if return_str:
        return out
    print(out)
    return None
```

All existing call sites require zero changes. No tests break.

**Do not implement until the GUI architecture is decided.** Adding the parameter now creates dead code. The moment the GUI phase is scoped, implement this first — it is a prerequisite for every GUI widget that shows system status.

---

## P3 — T-006: Observability & Instrumentation

**Severity:** None — no current user impact.  
**Impact:** Meaningful only once the codebase or contributor count grows.  
**Effort:** L | **Risk:** Low | **Blocked by:** Scale

Phase timing snapshots, per-check success/failure ratios, and metrics aggregation via an `@instrument` decorator or metrics registry. The debug logger already captures structured events; this would add aggregation and reporting on top.

**Defer explicitly.** A single-contributor CLI tool does not need a metrics registry. Revisit when the codebase exceeds ~10 K lines or a second contributor joins.
