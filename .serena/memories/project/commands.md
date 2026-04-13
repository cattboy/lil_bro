# Suggested Commands

## Environment
```bash
source .venv/Scripts/activate           # activate venv (Windows bash)
uv pip install -e ".[dev]"              # install all dev deps
uv pip install -e ".[dev,llm]"          # with LLM support
```

## Testing
```bash
source .venv/Scripts/activate && python -m pytest tests/ -v
source .venv/Scripts/activate && python -m pytest tests/test_config.py -v
source .venv/Scripts/activate && python -m pytest tests/ -x   # stop on first fail
```

## Linting / Formatting
- No explicit linter config found in pyproject.toml — follow existing code style
- Type hints used throughout; `Optional[X]` preferred over `X | None` for compat

## Run
```bash
source .venv/Scripts/activate && python -m src.main   # dev run
```

## Notes
- All temp files go in CWD via `get_temp_dir()` from `src/utils/paths.py`
- Docs go in `./docs/`
- gstack binaries at `.claude/skills/gstack/bin/` (project-local, not ~/.claude)
