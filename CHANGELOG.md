# Changelog

All notable changes to lil_bro are documented here.

## [0.4.0.0] - 2026-06-07

### Added
- **DLSS preset framework** — lil_bro resolves the forced DLSS preset from GPU capability (FP8 vs no-FP8) plus a quality/FPS lean, replacing the hardcoded per-generation letter. FP8 cards (RTX 40/50) get Preset **M** (quality) or **L** (FPS); non-FP8 (RTX 20/30) get **K**; GTX / Pascal / workstation GPUs are gated out with an explicit "DLSS not supported". The policy is baked-in Python constants (`src/utils/dlss_presets.py`), so updating for a new model is a one-line edit. See `docs/dlss_preset_framework.md`.
- **DLSS card quality/FPS toggle** — a Quality/FPS toggle on the Dashboard DLSS card flips the lean without editing config; the choice persists across runs (`QSettings`) and re-renders the recommended preset live. The toggle changes nothing on its own — only Apply writes the profile (approval-gated, revertible `.nip` backup).
- **Monitor-aware DLSS default** — at startup the recommended lean is seeded from the primary display (≤60 Hz or ≥4K → quality), overridable by the toggle or `lil_bro_config.json` (`nvidia.dlss.priority`).
- **Explain-why tooltip** on the DLSS card surfaces the model name, the quality/FPS tradeoff, and the ray-traced-denoiser caveat.
- **NVIDIA driver-profile Dashboard cards** — one-click apply for the full driver profile (G-Sync, VSync, FPS cap, ReBar, DLSS, power mode) and the DLSS-only preset, each gated by approval + a revertible `.nip` backup.
- **Thermal diagnostics** — environment probes and classified failure attribution for the thermal-monitoring sidecar.

### Changed
- **Shared `CardDialog` template** — every dialog now renders from one DESIGN.md card template (`src/gui/widgets/dialogs.py`); the stock `QMessageBox` dialogs and the bespoke confirm / admin / mouse-ready dialogs were migrated onto it.
- `lil_bro_config.json` gains an `nvidia.dlss.priority` setting (`quality` | `fps`), written on first run.

### Removed
- The hardcoded `DLSS_PRESETS` generation→letter dict, replaced by the capability-tier + priority service (`src/utils/dlss_presets.py`).

---

## [0.3.0.0] - 2026-06-02

### Added
- **WASD navigation layer** — a single application-level event filter maps `W` → proceed (clicks the active surface's default button) and `S` → back/escape (rejects a dialog, or routes the main window to the same Stop path `Esc` triggers), app-wide. It drives the existing actions rather than synthesizing key events, and stays inert while a text field (`QLineEdit` / `QTextEdit` / editable `QComboBox`) has focus, so typing "wasd" never navigates. Proceed/back controls now show `(W)` / `(S)` hints. See `src/gui/input/wasd_filter.py`.
- **Number-key fix selection** — rows in the batch fix dialog are numbered 1-9; pressing the matching digit toggles that fix, mirroring the CLI's "1 3" batch input.
- **Page-nav hotkeys** — `1` jumps to the Dashboard, `2` to Start Optimization (hints shown on the nav buttons). `WindowShortcut`-scoped, so modal dialogs keep digits 1-9 for fix selection.

### Changed
- **Session manifest moved to the CWD root and renamed** — the per-session revert record now writes to `lil_bro_session_manifest.json` next to the `.exe` and the logs (`lil_bro_actions.log` / `lil_bro_debug.log`), instead of being buried in `./lil_bro_backups/session_latest.json`. Every persistent lil_bro sidecar at the root now shares the `lil_bro_` prefix. NVIDIA profile backups follow suit (`lil_bro_nv_profile_*.nip`), kept inside `./lil_bro_backups/`.
- The Applied Fixes card's live-refresh watcher now watches the CWD root and guards on the manifest's `(mtime, size)` signature, so unrelated CWD activity (log writes, `_MEI*` / `./lil_bro/` temp dirs) no longer triggers a reload.

### Fixed
- **Main window now reliably comes to the foreground** after the splash closes — a Win32 `AttachThreadInput` + `SetForegroundWindow` sequence (with a taskbar-flash fallback) defeats the Windows foreground-lock that previously left lil_bro behind other windows, or only flashing in the taskbar, when the user clicked another app during the multi-second splash. Silent no-op off-Windows. See `src/gui/_foreground.py`.

---

## [0.2.0.0] - 2026-05-28

### Added
- **PySide6 desktop GUI** (~5,000 LOC under `src/gui/`). Replaces the prior CLI-only experience with a windowed app: dashboard with live thermals/mouse polling/monitor refresh tiles, optimization pipeline with phase-card progress, batch fix selection dialog, approval/confirm dialogs, AI Setup dialog with model download, animated splash screen. Five startup steps (theme/fonts → settings → bridge → LLM → spec dump) run before the main window appears. CLI mode is preserved via `lil_bro.exe --terminal`.
- **Stop button + global hotkeys** to cancel long-running benchmarks (Esc / Q / Return / Enter). Cancel signal routes through `Qt.DirectConnection` for reliable worker-thread wakeup, and the pipeline polls `_state.is_cancelled()` between phases.
- **GUI-mode output sinks** for `formatting.py` (`set_output_sink`), `progress_bar.py` (`set_progress_sink`), and approval/confirm handler registries. CLI mode falls back to direct stdout writes; GUI mode routes through Qt signals into the output panel.
- **Pipeline rescan idempotency** — running the optimization pipeline twice in one session now finds nothing the second time. `ScanPhase` always re-dumps live system specs (with the startup snapshot kept only as a degraded-mode fallback when the fresh dump fails); `FinalBenchPhase` skips with a distinct "no changes applied" message when `fixes_applied == 0`; the revert manifest accumulates across runs instead of being reset, so one Revert undoes every run's changes in newest-first order. See `docs/pipeline-rescan-idempotency-plan.md`.
- **Dashboard monitor refresh card** with a per-display "Fix Now" button that routes through the shared session manifest, so refresh-rate fixes triggered from the dashboard are revertible just like pipeline fixes.
- **`_MonitorRefreshWorker`** moves the 200-800ms ctypes `EnumDisplayDevicesW` + WMI fallback off the GUI thread when the user clicks Refresh on the empty-monitor card.
- **Atomic session manifest write** (`src/utils/revert.py`) — `.tmp` staging + `os.replace`. A process kill mid-write no longer wipes the session's revert data; worst case is the in-flight entry didn't land.
- **`src/agent_tools/quick_status.py`** — fast registry/QSettings reads for dashboard tile initialization without a full pipeline run.
- **`src/console_attach.py`** — Win32 console attach helper so `--terminal` cleanly attaches to the parent console or allocates a new one.

### Fixed
- **Dashboard "Fix Now" race conditions** — the monitor fix and monitor refresh paths now both reject clicks while the optimization pipeline is running and while the same worker is already in-flight, and `aboutToQuit` waits for both worker threads before LHM teardown. Without these guards a mid-pipeline fix could record stale "before" state in the manifest, breaking revert.
- **LHM sidecar startup on slow PCs and iGPUs** — readiness polling extended; partial-load conditions no longer flag as failures.
- **Cinebench cancellation under GUI mode** — the worker thread now honors `_state.is_cancelled()` mid-run, matching CLI cancel behavior.
- **Bundled-exe widget loading** — `'src.gui.widgets.status_bar_widget'` was missing from `lil_bro.spec` hiddenimports, causing the status bar to silently disappear in the bundled exe (the `try/except` in `app.py._on_finished` swallowed the `ImportError`).
- **LHM HTTP read size now capped at 10 MB** across the three call sites against `http://localhost:8085/data.json`. Defensive against another local process binding the port first; real responses are well under 500 KB.
- **`thermal_gate.run_thermal_guard` no longer fetches the LHM snapshot twice per benchmark**, removing the redundant HTTP round-trip and a dead unreachable branch.

### Changed
- **Major file refactors** for maintainability: `theme.py` split into a `theme/` package (7 modules), `cinebench.py` extracted into discovery / monitor / parser submodules, `lhm_sidecar.py` extracted into discovery / http / process_utils, `formatting.py` extracted `_console.py`, `app.run()` extracted `PipelineController` + `StartupCoordinator`. Behavior is unchanged; the goal was smaller, more readable files.
- **Terminal output formatting in the GUI output panel** — ANSI color codes are mapped to theme-aware hex colors; dividers and headers render at full panel width.
- **`src/llm/action_proposer.py`** — `_FALLBACK` renamed to public `FALLBACK_PROPOSALS`; new `propose_for_check()` helper. Dashboard tiles consume the same proposal templates as the CLI pipeline, so fix descriptions stay consistent across surfaces.
- **`StartupOrchestrator` now preloads `full_specs.json` on its worker thread** so the post-splash transition does no main-thread file I/O.

### Removed
- Duplicate `_on_benchmark_started` function definition in `src/gui/app.py` (signal binding selected the second copy; first was dead code).
- Stale "`_on_phase_changed = _on_benchmark_score`" alias and the dead `phase_changed` signal (`src/gui/signals.py`, `src/gui/app.py`). The signal was defined and connected to `_on_benchmark_score` but emitted by zero call sites: a gravestone left when `PhaseRow` was superseded by `BenchmarkRow` (driven by `benchmark_score_ready`). The signal and its `.connect()` wiring are removed; `_on_benchmark_score` now serves `benchmark_score_ready` alone.
- Redundant local `from PySide6.QtCore import QTimer` inside `Dashboard.set_monitor_data` (`QTimer` already imported at module scope).
- Duplicate inline comment in `DashboardWorker.start`.
- Unreachable branch in `thermal_gate.run_thermal_guard` after `require_thermal_protection` already returned True.
- Vacuous `test_no_lhm_returns_false` test that mocked an impossible production state to exercise the dead branch above.

### Security
- **Cinebench path** (`self.cinebench_path`) is now rejected if it contains a double-quote, preventing batch-file quote escape from a future caller passing arbitrary paths. `find_cinebench()` only returns hardcoded search results today; this is defense-in-depth.
- **`_find_elevated_pid(exe_name)`** validates `exe_name` against `^[\w.\-]+\.exe$` before interpolating it into the tasklist `/fi` filter. All current callers pass a hardcoded literal; the guard locks the function to safe inputs for any future caller.

### For contributors
- `CONTRIBUTING.md` "writing new checks" guide now references `FALLBACK_PROPOSALS` (was the renamed `_FALLBACK`).
- `_MonitorFixWorker` docstring corrected; added a warning that future fix handlers calling `prompt_approval` will deadlock if routed through a worker shaped like this one (no event loop on the worker thread).
- See `docs/lil_bro Design System/` for the design system, font/color preview pages, and the React/HTML/CSS kit the PySide6 QSS is modeled after.
- `lil_bro.spec` hiddenimports list now covers every module under `src/gui/widgets/`; per CLAUDE.md any new widget MUST be added there to avoid silent bundled-exe regressions.

---

## [0.1.1.0] - 2026-05-03

### Fixed
- **NVIDIA settings no longer falsely report as "misconfigured" after a saved-specs reload.** When `full_specs.json` was round-tripped through JSON, integer setting keys came back as strings, so every sub-checker silently read `None` and flagged the setting as wrong. Now the analyzer normalizes keys back to ints before comparing.
- **Cinebench actually shuts down when you abort it.** `start /b /wait` detaches Cinebench from the parent `cmd.exe` tree, so the previous `taskkill /T /PID` left a zombie `Cinebench.exe` running. Both the user-abort (Q/Enter) and watchdog-timeout paths now also issue `taskkill /IM Cinebench.exe`.
- **Cinebench window minimizes promptly even with the splash screen up.** Previously the title-based matcher missed the first ~100 s of the run because Cinebench 2026's splash window has no "cinebench" substring in its title. Now the helper matches by owning-process executable name and catches the splash within a couple of seconds of launch.
- **AMD-only systems get a clean "No NVIDIA GPU detected" message** instead of a raw subprocess error. NPI exits with `rc=3221225477` + a `DrsSession` NullRef in stderr when NVAPI fails to initialize; the collector now surfaces that as a structured error rather than reporting it as a generic NPI failure.

### Changed
- **NPI helpers consolidated into a single module.** `SETTING_IDS`, `TARGET_VALUES`, `DLSS_LETTER_MAP`, `DLSS_PRESETS`, `find_npi_exe`, `calculate_fps_cap`, and the new shared `export_current_profile` all live in `src/utils/nvidia_npi.py`. Net deletion of ~80 lines despite the new file: `nvidia_profile_dumper.py` shrinks 269→124, `nvidia_profile_setter.py` shrinks 287→221.
- `parse_nip` moved into `src/utils/nip_io.py`, killing the function-scope `from ..collectors.sub.nvidia_profile_dumper import parse_nip` workaround that papered over a circular import.
- `cinebench_timeout` default bumped from 600 s → 6000 s to support full-suite runs on thermally-throttled systems without false watchdog kills (single-test mode usually finishes in 10–30 minutes; full suite + slow hardware can run an hour-plus).
- `NvapiInitError(SetterError)` typed exception added to `src/utils/errors.py` so callers detect AMD-only systems by class match rather than string-matching the formatted error message.

### For contributors
- 450 tests total, all passing (was 442). 8 new tests cover the NvapiInitError raise/catch path, NvapiInitError subclass relationship, Cinebench user-abort taskkill, watchdog-timeout taskkill, and `_minimize_cinebench_window` abort short-circuit.
- `docs/DONE.md` (Issue 2.1) and Serena memory files updated to point at `src/utils/nvidia_npi.py` as the canonical home for the consolidated helpers.
- `CLAUDE.md` SETTING_IDS reference now points at the new module.
- `dist/lil_bro.exe` rebuilt against this branch.

---

## [0.1.0.0] - 2026-04-16

### Added
- **Revert/undo system** — You can now undo lil_bro's last session. Menu option 4 or `--revert` flag walks you through reverting each change individually: power plan, display settings, NVIDIA profile, and Game Mode. Non-revertible changes (temp cleanup) are clearly labeled. If anything goes wrong, System Restore Point fallback is offered.
- Session manifest (`session_latest.json`) records every fix applied with before/after state, enabling targeted per-fix rollback.
- `src/pipeline/phase_revert.py` — interactive revert UX with confirmation, per-fix status, and partial failure handling.
- `src/utils/revert.py` — revert handlers for power plan, game mode, NVIDIA profile, and display settings.
- `--revert` CLI flag for direct revert access without going through the menu.

### Changed
- Fix dispatch handlers now capture before-state and write manifest entries for each applied fix.
- `PipelineContext` gains `restore_point_created` field, threaded from bootstrap through approval flow.
- `nvidia_profile_setter.py` backups dir moved from `%APPDATA%` to CWD-relative `./lil_bro_backups/`.
- `create_restore_point()` now has a 4-minute timeout instead of hanging indefinitely.
- NVIDIA profile fix accepts `pre_backup_path` to avoid duplicate backup exports.

### Fixed
- Display revert now accepts `DISP_CHANGE_RESTART` (1) as success, not just `DISP_CHANGE_SUCCESSFUL` (0).
- Game mode revert uses canonical `set_game_mode()` instead of direct winreg writes.
- Absolute import in `nvidia_profile_setter.py` changed to relative for PyInstaller compatibility.
- `start_session_manifest()` now receives actual `restore_point_created` value instead of hardcoded `True`.

### For contributors
- 441 tests total, all passing. 5 new test files for revert feature coverage.
- `CLAUDE.md` updated with gstack skill routing rules.
- `pyproject.toml` gains `[tool.pytest.ini_options]` with explicit `testpaths`.

---

## [0.9.1] - 2026-04-06

### Added
- **NVIDIA Profile Inspector integration** — You can now detect and optimize driver-level GPU settings: detect misconfigured NVIDIA profiles, analyze setting deviations, and apply driver-level perf tuning fixes. Bundled C# NPI tool with Python integration layer.
- Dedicated NVIDIA GPU profile checks (`nvidia_profile.py`) and fixes (`nvidia_profile_setter.py`) in the optimization configuration phase.

### Fixed
- Thermal sidecar no longer spins up twice — startup LHM instance is now cleanly passed through the pipeline instead of creating a second sidecar.
- Cinebench process cleanup — now properly kills hanging benchmark processes on timeout instead of leaving zombie processes.
- Temp file cleanup — all subprocess artifacts (including `.nip` files from NPI) now go to CWD instead of `%TEMP%`, and stale `_MEI*` directories from crashed runs are cleaned up on exit.
- Thermal gate initialization error and silent exception handling improved with better logging.

### Changed
- **Pipeline architecture** — Refactored from a monolithic `phases.py` (220 lines) into a modular Phase protocol system: each of the 5 phases (bootstrap, scan, baseline, config, final) is now a separate class with a `run(ctx)` method, sharing state via a `PipelineContext` dataclass. Cleaner orchestration, easier to test, easier to modify.
- Fix dispatch registry now uses a decorator pattern (`@register_fix`) instead of a manual dict.
- Consolidated duplicate `is_admin()` checks into a single canonical source in `src/utils/platform.py`.
- Cleaned up debug variable names (`_UNICODE_SAFE` → `_ASCII_FALLBACK`) and removed dead code for clarity.
- Windows registry imports made lazy in several modules for better cross-platform test support.
- LLM retry errors now logged to debug log instead of silently swallowed.

### For contributors
- 557 new tests for NVIDIA Profile Inspector integration (including full NPI setting parser tests, profile detection, and fix application). 882 tests total, all passing.
- Pipeline phases are now independently testable via the Phase protocol.
- `CLAUDE.md` updated with phase architecture, NPI collector reference, and subprocess temp file rules.

---

## [0.9.0] - 2026-03-31

### Added
- `--debug` flag: run `lil_bro.exe --debug` to capture internal phase events, collector errors, and warnings to `./lil_bro_debug.log` at CWD root. Completely silent by default — no file created, no overhead.
- Post-run cleanup (`post_run_cleanup.py`): the `./lil_bro/` working directory is automatically removed on exit, keeping the portable .exe folder clean between runs. Persistent logs (`lil_bro_actions.log`, `lil_bro_debug.log`) live at CWD root and survive cleanup.

### Fixed
- `full_specs.json` now saves to `./lil_bro/full_specs.json` — it was incorrectly placed inside `./lil_bro/logs/` (a subdirectory reserved for logs, not data snapshots).

### Changed
- Action log (`lil_bro_actions.log`) now captures the full app session — the session start banner writes before the startup thermal scan, so every sidecar activity falls inside the log boundary.
- Fix dispatch and user approval decisions are now recorded with outcome tags: `[PASS]`/`[FAIL]` per fix, `[APPROVED]`/`[SKIPPED]` per proposal group. The log is now a complete audit trail for every system change lil_bro makes.
- `action_logger.log_action()` gains an optional `outcome` keyword — existing callers are unchanged, new callers can tag entries for programmatic parsing.

### For contributors
- 17 new tests: `test_debug_logger.py` (8 tests — singleton, no duplicate handlers, disabled/enabled path, file write, warning/debug level), `test_action_logger.py` (9 tests)
- 13 additional tests for action logger v2 (outcome param, dispatch/result logging, approval decisions). 325 tests total, all passing.

---

## [0.8.0] - 2026-03-28

### Added
- Custom `lhm-server.exe` is now bundled inside the portable .exe — no separate install needed. The sidecar runs LibreHardwareMonitorLib with the PawnIO kernel driver for ring-0 temperature access on modern Windows.
- `update_pawnio.ps1`: automatically fetches the latest WHQL-signed `PawnIO.sys` from namazso/PawnIO.Setup GitHub releases before each build. Falls back to WDK source compilation if offline.
- `install_deps.ps1`: one-command dev environment setup — installs Python, uv, .NET 8 SDK, WDK, and initializes submodules.
- CPU sensor derivation rewritten: now correctly picks `CPU Package` → `Tctl/Tdie` → safe CPU fallback, with full AMD Ryzen support. Hotspot, VRM, and Core Max sensors are excluded to avoid false positives.

### For contributors
- Build pipeline expanded to 5 steps: Clean → PawnIO fetch → lhm-server build → PyInstaller → integrity manifest.

## [0.7.0] - 2026-03-25

### Changed
- `main.py` trimmed from 549 lines to 48 — all pipeline logic now lives in `src/pipeline/` (8 modules: `banner`, `menu`, `approval`, `fix_dispatch`, `thermal_gate`, `phases`, `_state`)
- Auto-fix dispatch now uses a clean registry dict (`FIX_REGISTRY`) instead of an if-elif chain — adding a new auto-fixable check is now a one-liner
- Thermal safety gate deduplicated — the 14-line pre-benchmark check that was copy-pasted in Phase 3 and Phase 5 is now a single reusable function
- Shared LLM state managed via `get_llm()`/`set_llm()` in `_state.py` — eliminates the Python name-binding bug that would occur with `from module import _llm`
- `FIX_REGISTRY` type annotation corrected from `callable` builtin to `Callable[[dict], bool]` from `collections.abc`

### For contributors
- 31 new tests: `test_parse_selection.py` (12 edge cases), `test_thermal_gate.py` (6 paths), `test_fix_dispatch.py` (13 — full coverage of all 4 dispatch handlers)
- 246 tests total, all passing. QA health: 98/100.

## [0.6.0] - 2026-03-24

### Added
- Unicode/ASCII fallback system — terminal icons gracefully degrade on non-UTF-8 terminals (Windows CMD, piped stdout, frozen builds)
- `print_key_value()` helper for consistent label:value display with dim labels and colored values
- `print_section_divider()` for terminal-width divider lines with optional centered labels
- `print_prompt()` with `> ` prefix for branded input prompts
- `print_dim()`, `print_accent()`, `print_audit_summary()`, `print_finding()`, `print_proposal()`, `prompt_confirm()` — centralized formatting helpers
- `Fore.BLUE` mapped in DESIGN.md colorama section for info/secondary color
- TODOS.md for tracking deferred work from reviews
- 27 new tests covering all formatting functions, Unicode detection, DESIGN.md sync

### Changed
- Progress bar now dynamically sizes to terminal width instead of fixed 30-char width
- Progress bar uses ASCII characters (`# = - .`) on non-UTF-8 terminals instead of Unicode block elements
- Hardware summary in pipeline output uses `print_key_value()` instead of inline colorama
- AI Model status display uses `print_key_value()` with color-coded status
- Menu options use cyan-numbered formatting with `print_prompt()` for input
- `model_loader.py` migrated from inline colorama to formatting helpers (`print_accent`, `print_error`, `print_warning`, `print_header`, `print_success`, `print_step`, `prompt_confirm`)
- `action_logger.py` migrated from inline `Style.DIM` to `print_dim()`
- `print_proposal()` hierarchy fixed: explanation uses `Fore.WHITE`, fix line uses `Style.DIM`
- Banner subtitle uses `print_accent()`, privacy line uses `print_dim()`
- Mouse polling prompt reworded to match brand voice

### Removed
- Redundant `colorama.init()` call in `main.py` (now handled once in `formatting.py`)
- Inline colorama formatting throughout `main.py` and `model_loader.py`

## [0.5.0] - 2026-03-23

### Added
- Game Mode auto-fix via registry write
- Thermal fallback template for LLM-unavailable scenarios
- Brand voice idle thermal warnings
- Animated progress bar with plasma-sweep glow
- NVIDIA driver version display in hardware summary
- `_safe_collect` wrapper for collector resilience
- 188 tests covering all agent tools, collectors, and utilities
