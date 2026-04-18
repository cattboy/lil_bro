# Feature Plan: Revert Last Session

**Created:** 2026-04-13  
**Branch:** feature/revert-last-session (cut from refactor/priority-1-improvements or main)  
**Design review:** 1/10 → 9/10 (9 decisions locked, 0 deferred)  
**Status:** Ready for eng review

---

## Problem

After lil_bro applies fixes, users have no way to undo them if something goes wrong or they simply dislike the changes. A System Restore Point is created before every run, but it's a sledgehammer — it reverts the entire system, including changes the user made after lil_bro ran, and takes minutes. Users need a fast, precise undo.

---

## Approach

**Granular per-fix backups + System Restore Point as last resort.**

Before each fix is applied, the fix function captures the current ("before") state and appends it to a session manifest JSON file at `./lil_bro_backups/session_latest.json`. If the user invokes revert, lil_bro walks the manifest in reverse and restores each previous value. If any individual revert fails, lil_bro launches `rstrui.exe` (Windows System Restore) and directs the user to select the pre-lil_bro restore point.

The NVIDIA profile setter already backs up `.nip` files. This feature moves that backup to `./lil_bro_backups/` (a persistent CWD-root directory that survives `_cleanup_cwd_tempdir()`) and extends the pattern to all revertible fixes.

---

## Design Decisions (locked)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Entry point | Menu option 4 "Revert last session" + `--revert` CLI flag | Discoverable without being intrusive on happy-path runs |
| Backup architecture | Granular per-fix + restore point fallback | Precise, fast, works even if System Restore is disabled |
| Revert scope (v1) | All-or-nothing | Avoids system state sync issues from partial reverts |
| Session history | Last session only | Simplest; users revert within minutes, not days |
| Capture timing | Inside each fix function, before applying | Atomic with the change; follows existing NVIDIA pattern |
| Backup lifetime | Persists across cleanup | Excluded from `post_run_cleanup.py` deletion |
| Partial failure | Continue + offer restore point | Better than halting mid-revert in an intermediate state |
| Irreversible fixes | Show in "Cannot revert" section with explanation | Transparency builds trust |
| Brand voice | Casual, lowercase success/error lines per DESIGN.md | "you're back to factory lil_bro. everything's where you left it." |

---

## Terminal UX

### Revert confirmation screen

```
┌─ REVERT LAST SESSION ───────────────────────────────┐
│                                                      │
│  found your session backup from 2026-04-13 14:30     │
│                                                      │
│  Revertible (3):                                     │
│    Power Plan      Balanced ← High Performance       │
│    Game Mode       OFF      ← ON                     │
│    NVIDIA Profile  .nip backup available             │
│                                                      │
│  Cannot revert (1):                                  │
│    Temp cleanup    3.2 GB recovered — files gone     │
│                    (it was junk, don't worry)        │
│                                                      │
│  Revert 3 changes? [y/N]                            │
└──────────────────────────────────────────────────────┘
```

### Progress (after confirmation)

```
Reverting session changes...

  [OK] Power Plan       ← Balanced
  [OK] Game Mode        ← OFF
  [OK] NVIDIA Profile   ← original .nip restored

you're back to factory lil_bro. everything's where you left it.
```

### Partial failure

```
  [OK] Power Plan       ← Balanced
  [FAIL] NVIDIA Profile  — NPI.exe not found

2 of 3 changes reverted.

the nuclear option is available (System Restore Point).
it'll roll back your whole system, not just lil_bro's work.
want to use it? [y/N]
```

### Empty state

```
no session backup found. either lil_bro hasn't run yet,
or the last session made no changes.
```

---

## Session Manifest Schema

**Path:** `./lil_bro/session_backups/session_latest.json`  
**Written:** At start of each new run (overwrites previous — not at exit, so a crashed run doesn't destroy the last good backup)

```json
{
  "session_id": "20260413_143022",
  "session_date": "2026-04-13T14:30:22",
  "restore_point_created": true,
  "fixes": [
    {
      "fix": "power_plan",
      "revertible": true,
      "before": { "guid": "381b4222-f694-41f0-9685-ff5bb260df2e", "name": "Balanced" },
      "after":  { "guid": "8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", "name": "High Performance" },
      "applied_at": "2026-04-13T14:31:05"
    },
    {
      "fix": "game_mode",
      "revertible": true,
      "before": { "AutoGameModeEnabled": 0 },
      "after":  { "AutoGameModeEnabled": 1 },
      "applied_at": "2026-04-13T14:31:07"
    },
    {
      "fix": "nvidia_profile",
      "revertible": true,
      "before_backup": "./lil_bro/backups/nv_profile_20260413_143100.nip",
      "applied_at": "2026-04-13T14:31:10"
    },
    {
      "fix": "temp_audit",
      "revertible": false,
      "reason": "Deleted temp files cannot be restored",
      "display": "3.2 GB recovered — files gone",
      "applied_at": "2026-04-13T14:31:15"
    },
    {
      "fix": "display",
      "revertible": true,
      "before": { "device": "\\\\.\\DISPLAY1", "width": 2560, "height": 1440, "hz": 60 },
      "after":  { "device": "\\\\.\\DISPLAY1", "width": 2560, "height": 1440, "hz": 144 },
      "applied_at": "2026-04-13T14:31:20"
    }
  ]
}
```

---

## Files to Create / Modify

### New files

| File | Purpose |
|------|---------|
| `src/utils/revert.py` | Session manifest read/write + revert orchestration + per-fix revert functions |
| `src/pipeline/phase_revert.py` | Terminal UX for the revert flow (display summary, confirmation, progress) |

### Modified files

| File | Change |
|------|--------|
| `src/utils/paths.py` | Add `get_session_backup_path()` → `./lil_bro_backups/session_latest.json`; move `get_backups_dir()` here pointing to `./lil_bro_backups/` |
| `src/main.py` | Add `--revert` CLI flag (argparse) |
| `src/pipeline/menu.py` | Add menu option 4 "Revert last session" (always shown; shows empty state if no manifest) |
| `src/pipeline/approval.py` | Call `start_session_manifest()` at start of fix loop (just before `bar.start()`); show visible warning if write fails |
| `src/pipeline/fix_dispatch.py` | Each `_fix_*` wrapper captures before-state + calls `append_fix_to_manifest()` before applying the fix |
| `src/agent_tools/nvidia_profile_setter.py` | Update `get_backups_dir()` import to use `paths.get_backups_dir()` |
| `src/agent_tools/display_setter.py` | Add `get_current_display_mode(device_name: str) -> DEVMODE \| None` public wrapper around `_get_current_mode()` |
| `src/bootstrapper.py` | Add `timeout=240` to `subprocess.run()` in `create_restore_point()` — 4 min allows for slow hardware |

**NOT touching:** `src/pipeline/post_run_cleanup.py` (backup dir is at CWD root, outside cleanup scope), `src/pipeline/base.py` (singleton approach, no PipelineContext change)

---

## Revert Implementation Details

### `src/utils/revert.py`

```python
# Key functions:
def start_session_manifest(manifest_path: str, restore_point_created: bool) -> None:
    """Write a fresh manifest at the start of each run. Overwrites previous."""

def append_fix_to_manifest(manifest_path: str, entry: dict) -> None:
    """Thread-safe append of a fix entry. Called by each fix function before applying."""

def load_manifest(manifest_path: str) -> dict | None:
    """Load manifest from disk. Returns None if not found or corrupt."""

def revert_fix(entry: dict) -> tuple[bool, str]:
    """Dispatch revert for a single fix entry. Returns (success, error_msg)."""

def trigger_system_restore() -> bool:
    """Call Restore-Computer via PowerShell. Returns success bool."""
```

### Per-fix revert dispatch

| Fix key (actual) | Revert method |
|-----------------|--------------|
| `power_plan` | `powercfg /setactive <before.guid>` |
| `game_mode` | `winreg.SetValueEx(... before.AutoGameModeEnabled)` |
| `nvidia_profile` | `npi.exe -importProfile <before_backup_path>` (warn: wipes NVIDIA changes made after lil_bro ran) |
| `display` | `ChangeDisplaySettingsEx` with before `DEVMODE` (show device name in summary) |
| `temp_folders` | Non-revertible — display note only, no action |
| `rebar` | Read-only check — no fix applied, no revert needed |
| `xmp_check` | Read-only check — no revert needed |
| `mouse` | Read-only — no revert needed |

Note: manifest uses the actual `@register_fix` key names (e.g., `"temp_folders"`, not `"temp_audit"`).

### trigger_system_restore() implementation

```python
def trigger_system_restore(session_date: str) -> bool:
    """Launch Windows System Restore UI and direct user to the pre-lil_bro restore point."""
    try:
        subprocess.Popen(["rstrui.exe"])
        print_info("Windows System Restore has opened.")
        print_info(f"Select the restore point labelled:")
        print_info(f"  'lil_bro Pre-Tuning {session_date}'")
        print_info("and follow the prompts to roll back your system.")
        return True
    except Exception as e:
        print_error(f"Could not launch System Restore: {e}")
        print_info("Run rstrui.exe manually from Start to access System Restore.")
        return False
```

---

## Manifest Writer Injection Pattern

**Singleton import (only approach for v1).** `fix_dispatch.py` and `revert.py` import `get_session_backup_path()` directly from `paths.py`. No PipelineContext change. Consistent with how `action_logger` is used throughout. Fixes are sequential so no threading concern.

On manifest write failure: call `print_warning("Revert will not be available for this session — backup could not be saved.")` and log via `action_logger`. The fix proceeds regardless. Silent-only failure is not acceptable for a safety feature.

---

## Revert Flow (phase_revert.py)

```
1. Load manifest from get_session_backup_path()
   → If not found: print empty state message, exit
2. Display summary screen (revertible vs cannot-revert sections)
3. prompt_approval("Revert N changes?")
   → If no: exit
4. For each fix in manifest (in reverse applied_at order):
   → print_step(f"Reverting {fix}...")
   → if entry["revertible"]: call revert_fix(entry)
     → print_step_done(success=True/False)
     → if False: record failure
   → else: skip (non-revertible, already shown in summary)
5. If all succeeded: print success + brand voice exit line
6. If any failed: print partial result + offer restore point
   → prompt_approval("Use System Restore Point for what's left?")
   → if yes: trigger_system_restore()
7. log_action("Revert", ...) for the session
```

---

## Testing Requirements (~22 new tests)

### revert.py
- `start_session_manifest()` happy path — manifest file created with correct schema
- `start_session_manifest()` → `lil_bro_backups/` auto-created if directory missing
- `start_session_manifest()` OSError (disk full) → log + continue, no raise
- `append_fix_to_manifest()` happy path — entry appended to fixes array
- `append_fix_to_manifest()` write failure → `print_warning()` called, no raise (fix proceeds)
- `append_fix_to_manifest()` corrupt manifest JSON → graceful handle, no raise
- `load_manifest()` file not found → returns None (empty state)
- `load_manifest()` JSON parse error → returns None (not raise)
- `revert_fix()` power_plan → mocked `powercfg /setactive` called with before.guid
- `revert_fix()` game_mode → mocked `winreg.SetValueEx` called with before value
- `revert_fix()` nvidia_profile → mocked `npi.exe -importProfile` called
- `revert_fix()` nvidia_profile with missing .nip path → returns (False, error_msg)
- `revert_fix()` display → mocked `ChangeDisplaySettingsEx` called with before DEVMODE
- `revert_fix()` unknown fix key → returns (False, "No revert handler for '...'")
- `trigger_system_restore()` → mocked `subprocess.Popen(["rstrui.exe"])` called, returns True
- `trigger_system_restore()` subprocess failure → returns False, `print_error()` called

### phase_revert.py
- Empty state (no manifest) → prints "no session backup found" and exits
- All non-revertible entries → "Cannot revert" section shown, 0 revertible count
- User declines confirmation → exits without calling revert_fix()
- All reverted successfully → success message printed
- One fix fails → partial result shown, `trigger_system_restore()` offered
- All fixes fail → all failures shown, restore point offered
- User declines restore point after failure → exits cleanly

### fix_dispatch.py modifications
- `_fix_power_plan` → `get_active_power_plan()` fails, manifest entry skipped, fix proceeds anyway
- `_fix_power_plan` → manifest write fails, `print_warning()` called, fix proceeds

### menu.py / main.py
- Menu choice '4' routes to phase_revert flow
- `--revert` flag bypasses menu, routes directly to phase_revert flow

---

## Not In Scope (v1)

- **Selective per-fix revert** (checkbox UI) — v2
- **Multi-session history** (last 3 sessions) — v2
- **Revert summary in the action log email/export** — v2

---

## Open Question for Eng Review

- Should `append_fix_to_manifest()` be a thread-safe singleton (like `action_logger`) or a simple write-on-call function? Fixes are sequential in v1 so it doesn't matter yet, but the pattern choice affects v2 extensibility.

---

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 1 | CLEAN | 10 findings reviewed, 4 accepted cross-model tensions |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAN (PLAN) | 7 issues found + fixed, 12 test gaps added, 0 unresolved |
| Design Review | `/plan-design-review` | UI/UX gaps | 1 | CLEAN (FULL) | score: 1/10 → 9/10, 9 decisions |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | — |

**VERDICT:** ENG + DESIGN CLEARED — ready to implement.
