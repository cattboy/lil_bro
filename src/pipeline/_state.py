"""
Shared mutable state for the pipeline.

The LLM instance is loaded once via the AI Setup menu and reused
across pipeline runs. Storing it here avoids circular imports
between menu.py and phases.py.

IMPORTANT: Never write `from src.pipeline._state import _llm` — that
creates a local binding that never sees updates. Always use the
getter/setter functions.
"""

_llm = None


def get_llm():
    """Returns the current LLM instance (may be None)."""
    return _llm


def set_llm(instance):
    """Sets the LLM instance after loading."""
    global _llm
    _llm = instance
