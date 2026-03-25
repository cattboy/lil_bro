# Changelog

All notable changes to lil_bro are documented here.

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
