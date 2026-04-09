# Tech Stack

- **Language**: Python 3.11+
- **Package manager**: `uv` (never pip directly); deps in `pyproject.toml`
- **Venv**: `.venv/` at project root; activate with `source .venv/Scripts/activate` (Windows bash)
- **LLM**: `llama_cpp` (optional, lazy import via TYPE_CHECKING guard)
- **System access**: ctypes, winreg, WMI, subprocess
- **Testing**: pytest (`tests/` directory); current count ~387 tests
- **Build**: PyInstaller (`lil_bro.spec`), `build.py`
- **Terminal UI**: Rich-style formatting via `src/utils/formatting.py` — no GUI

## Key optional dependency pattern
```python
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from llama_cpp import Llama  # type: ignore
# then use: Optional["Llama"] or Optional[Llama]
```
