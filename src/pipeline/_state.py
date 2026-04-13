"""
Shared mutable state for the pipeline.

The LLM instance is loaded once via the AI Setup menu and reused
across pipeline runs. Storing it here avoids circular imports
between menu.py and phases.py.

IMPORTANT: Never write `from src.pipeline._state import _llm` — that
creates a local binding that never sees updates. Always use the
getter/setter functions.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from llama_cpp import Llama  # type: ignore

_llm: Optional[Llama] = None


def get_llm() -> Optional[Llama]:
    """Returns the current LLM instance (may be None)."""
    return _llm


def set_llm(instance: Optional[Llama]) -> None:
    """Sets the LLM instance after loading."""
    global _llm
    _llm = instance
