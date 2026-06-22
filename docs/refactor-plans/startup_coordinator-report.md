# Refactor report: src/gui/startup_coordinator.py

Branch: `Refactor/v0.5.1.0` · Pattern 4 (Decompose a God-Class) via mixins.

## Outcome
- **Before:** `startup_coordinator.py` = **963 lines** (one `StartupCoordinator(QObject)` god-class, ~38 methods).
- **After (target file):** **123 lines** — `__init__`, the two shared helpers
  (`_ensure_restore_point_choice`, `_on_card_fix_result`), `StartupCompleter`, composing five
  mixins with `QObject` rightmost.
- **New modules** (all `src/gui/`):
  | Module | Lines | Holds |
  |---|---|---|
  | `_startup_sections.py` | 32 | `_FIX_TO_SECTIONS` + `_sections_for_fixes` |
  | `_startup_manifest_watcher.py` | 107 | `ManifestWatcherMixin` |
  | `_startup_wiring.py` | 172 | `StartupWiringMixin` |
  | `_startup_dashboard_refresh.py` | 223 | `DashboardRefreshMixin` |
  | `_startup_card_fixes_device.py` | 240 | `DeviceFixMixin` (monitor + NVIDIA) |
  | `_startup_card_fixes_setting.py` | 228 | `SettingThermalFixMixin` (power/game/HAGS + thermal) |
- **Net code change:** ~+162 lines across the family (123 + 1002 new = 1125 vs 963) — the delta is
  per-module docstrings, imports, and `TYPE_CHECKING` contract stubs. No new file exceeds the
  300-line threshold; `startup_coordinator.py` no longer appears in the discovery report.
- **`app.py` unchanged** — every `startup.<method>` signal connection still resolves (mixins keep
  all methods bound to the single QObject instance).

## Chunks completed
| # | Description | Commit |
|---|---|---|
| 1 | Characterization tests for untested symbols | `607b3d3` |
| 2 | Extract `_startup_sections` (Pattern 6 warm-up) | `aadb9cb` |
| 3 | Extract `ManifestWatcherMixin` | `bab8176` |
| 4 | Extract `StartupWiringMixin` | `0f7fe58` |
| 5 | Extract `DashboardRefreshMixin` | `9e413ec` |
| 6 | Extract `DeviceFixMixin` (monitor + NVIDIA) | `1a6da72` |
| 7 | Extract `SettingThermalFixMixin`; finish split | `827382c` |
| 8 | PyInstaller spec hiddenimports | `257f593` |
| 9 | ARCHITECTURE.md + DEVELOPMENT.md sync | `b4b9769` |

Each chunk was one atomic commit; the suite was green between chunks.

## Test suite
- Before: **1229** passing. After: **1267** passing (+38).
- Added: characterization tests for the previously-untested symbols (`on_finished`, thermal-retry
  flow, `_ensure_restore_point_choice`, `_on_card_fix_result`, `StartupCompleter`, `on_lhm_ready`,
  `on_step`, `_reload_last_run`, `on_hags_fix_requested`, result/cleanup slots) + two composition
  guards (MRO/base-list lock + `_startup_sections` re-export identity).
- GUI smoke: `python scripts/mock_gui.py --smoke` → `[smoke] OK` (incl. busy-cue lock/reset canary).

## Mechanism notes (for future runs of this skill)
- The `class X(QObject):` base-list line can't be changed by built-in `Edit` (serena_guard blocks
  edits overlapping a class symbol) nor by Serena `replace_symbol_body` (needs the whole class).
  **`mcp__serena__replace_content`** (a Serena tool, not hook-gated) was the right instrument for
  base-list changes, method removal, and import edits — `literal` mode with verbatim text, or
  `regex` with `.*?` (DOTALL) between unique anchors.
- **Pitfall:** `replace_content` in **regex** mode treats `\n` in `repl` as a literal backslash-n,
  not a newline (it corrupted the file tail once; caught by an `ast.parse` check and fixed). Use
  `$!1` backreferences to carry forward captured whitespace instead of emitting `\n`; use `literal`
  mode with an actual newline when a newline is required.
- `safe_delete_symbol` was unusable here — it refuses when references exist, and every moved method
  is referenced.
- @Slot-on-plain-mixin under QueuedConnection: confirmed safe (Phase-4 probe + the real-thread
  anchoring test stayed green) — Shiboken scans the full MRO, so inherited slots register.

## Devil's advocate concerns addressed
- "Green suite proves nothing" for untested movers → Chunk 1 added characterization tests first.
- Pyright unknown-attr on cross-class calls → `TYPE_CHECKING` attribute + method stubs in each mixin.
- rm+Write reconstruction hazard → avoided entirely (used `replace_content`, not file rewrites);
  every chunk verified by `git diff` review + the test gate.

## Deferred follow-ups
- **Test patch-target debt:** card-fix tests patch `QThread`/`_*Worker` at module paths. The
  refactor repointed `QThread` patches to the new mixin modules (and dropped the now-unused
  `QThread` import from `startup_coordinator`); worker patches remain at `src.gui.worker.*` (source)
  and were unaffected. No action needed — noted for awareness.
- **Other test-count references:** `CLAUDE.md` ("Current test count: 1229") and `docs/ROADMAP.md`
  still say 1229 — out of scope for this refactor (user scoped docs to ARCHITECTURE + DEVELOPMENT);
  sync on next release.
- **dist/lil_bro.exe not rebuilt** — this is a refactor branch with no version bump; rebuild belongs
  to `/ship`. The spec was updated so the next build picks up the new modules.
- **Next decomposition candidates** (from the re-run discovery): `dashboard.py` (802),
  `coachmarks.py` (658), `pipeline_controller.py` (508).

## PyInstaller note
Six new modules under `src/gui/` (not `src/gui/widgets/`) were added to `lil_bro.spec`
`hiddenimports` (`257f593`). They are top-level imports of `startup_coordinator`, so PyInstaller
would follow them regardless; the explicit entries match spec policy.
