---
name: testing_patterns
description: Test suite conventions — all mocked, no real system calls, pytest, ~387 tests
type: project
---

# Testing Patterns

## Core rule: all mocked, no real system calls

Every test patches system-level calls. The suite must run on any machine without admin rights or specific hardware.

Always mock:
- `wmi.WMI()` — WMI queries
- `winreg.*` — registry access
- ctypes calls — Win32 API (EnumDisplaySettings, GetCursorPos, etc.)
- `subprocess.run` / `subprocess.Popen` — external processes
- nvidia-smi, dxdiag, LHM HTTP API responses
- File I/O for temp paths

Never write tests that hit real hardware, the registry, or external processes.

## Location & count

- All tests live in `tests/`
- Current count: ~387 tests
- Framework: pytest

## Run commands

```bash
# Full suite
source .venv/Scripts/activate && python -m pytest tests/ -v

# Stop on first failure
source .venv/Scripts/activate && python -m pytest tests/ -x

# Single file
source .venv/Scripts/activate && python -m pytest tests/test_foo.py -v

# Single test
source .venv/Scripts/activate && python -m pytest tests/test_foo.py::test_bar -v
```

## What NOT to test via Serena

Do not suggest integration tests that require:
- Admin elevation
- Real GPU / CPU hardware
- Live WMI or registry state
- Running Cinebench or LHM

These are out of scope for the automated test suite.
