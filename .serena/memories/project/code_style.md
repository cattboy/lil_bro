# Code Style & Conventions

## Naming
- snake_case for functions/variables/files
- PascalCase for classes
- UPPER_SNAKE for constants (e.g., `_SKIP_RESULT`, `_WATCHDOG_THRESHOLD`)
- Private module state prefixed with `_` (e.g., `_llm`, `_state.py`)

## Type hints
- Used throughout; `Optional[X]` style (not `X | None`)
- Optional dependencies use `TYPE_CHECKING` guard + string annotations
- `from typing import Optional, TYPE_CHECKING` at top of file

## Error handling
- Custom hierarchy: `LilBroError` → `ScannerError`, `SetterError`, `RestorePointError`, `AdminRequiredError`
- Setters raise `SetterError`; collectors return `{"error": str}` dict on failure
- No bare `except:` — always catch specific exceptions or `Exception` with logging

## Return dicts
- Agent tool checks return `{"status": "OK"|"WARN"|"FAIL"|"SKIPPED", "message": str, ...}`
- Collectors return nested dicts with `{"error": str}` sub-keys on partial failure

## Imports
- Standard lib → third-party → local (`src.*`)
- No relative imports; always `from src.xxx import yyy`

## File layout
- `src/agent_tools/` — system check + setter pairs (e.g., `nvidia_profile.py` + `nvidia_profile_setter.py`)
- `src/collectors/sub/` — hardware data collectors
- `src/pipeline/` — orchestration, phases, approval, dispatch
- `src/utils/` — shared utilities (errors, formatting, logging, paths)
- `src/llm/` — model loader + action proposer
- `src/benchmarks/` — Cinebench runner + thermal monitor
