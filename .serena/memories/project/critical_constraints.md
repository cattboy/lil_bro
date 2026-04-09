---
name: critical_constraints
description: Non-negotiable safety and architectural rules with exact function names — must be verified before writing any new code
type: project
---

# Critical Constraints

## 1. Approval gate — non-negotiable

Every system modification must call `prompt_approval()` before executing.

- **Function**: `prompt_approval()` in `src/pipeline/approval.py`
- **Routing**: `fix_dispatch` registry in `src/pipeline/fix_dispatch.py`
- **Flow**: check → `fix_dispatch` → `run_approval_flow` → `prompt_approval()` → setter

No silent changes, ever. The `safety-reviewer` Claude Code agent flags any bypass of this gate.

## 2. Temp files — always use get_temp_dir()

All subprocess temp files must use `get_temp_dir()` from `src/utils/paths.py` as the `dir=` argument.

```python
import tempfile
from src.utils.paths import get_temp_dir

with tempfile.TemporaryDirectory(dir=str(get_temp_dir())) as tmp:
    ...

fd, path = tempfile.mkstemp(dir=str(get_temp_dir()))
```

Never use system default temp (`%TEMP%` / `tempfile.gettempdir()`).  
**Why**: all runtime artifacts must live under `./lil_bro/` for deterministic cleanup via `post_run_cleanup.py`.

## 3. Package manager — always uv

```bash
source .venv/Scripts/activate   # activate first
uv pip install -e ".[dev]"      # never: pip install
```

Never use `pip install` directly. All dependencies declared in `pyproject.toml`.

## 4. No relative imports

Always `from src.xxx import yyy` — never `from .foo import bar` or `from ..bar import baz`.

## 5. External HTTP — restricted

No HTTP calls except:
1. Driver version checks from vendor URLs (NVIDIA/AMD/Intel)
2. One-time GGUF model download from HuggingFace on first run

No telemetry, no cloud APIs, no analytics.

## 6. Optional dependency pattern

For `llama_cpp` and other optional heavy deps:

```python
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from llama_cpp import Llama  # type: ignore

def my_func(llm: Optional["Llama"] = None) -> None: ...
```
