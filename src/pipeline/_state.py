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



# --- Cooperative cancel ---------------------------------------------------
# CLI mode leaves ``_CANCEL_CHECK`` as None; ``is_cancelled()`` always
# returns False, so existing pipeline runs are unaffected. The GUI's
# PipelineWorker installs a check at startup that returns True when the
# user clicks Cancel — phases.py and phase_config.py poll this between
# work units. (Cinebench subprocess does NOT support graceful cancel —
# documented limitation in README.)
_CANCEL_CHECK = None


def set_cancel_check(check) -> None:
    """Install (or clear) a cooperative-cancel check callable.

    Callable signature: ``() -> bool`` — return True to request cancel.
    Pass ``None`` to clear (CLI fallback).
    """
    global _CANCEL_CHECK
    _CANCEL_CHECK = check


def is_cancelled() -> bool:
    """Return True if the GUI worker has requested cancel."""
    check = _CANCEL_CHECK
    return bool(check()) if check is not None else False
