# Changelog

All notable changes to lil_bro are documented here.

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
