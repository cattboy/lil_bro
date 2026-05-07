"""Verifies the prompt_approval / prompt_confirm handler-registry pattern.

The critical property is **late lookup** — ``prompt_approval`` must read
``_APPROVAL_HANDLER`` at call time, not at import time. If a downstream
module imports ``prompt_approval`` before the GUI bridge installs its
handler, swapping the handler later must still be honored.

These tests also guard the safe-default behavior: clearing the handler
restores CLI input(), and a handler return value is propagated verbatim.
"""

from __future__ import annotations

from src.utils import formatting
from src.pipeline import approval as approval_module  # late-import consumer


def test_set_approval_handler_intercepts_call(monkeypatch):
    captured: list[str] = []

    def handler(action: str) -> bool:
        captured.append(action)
        return True

    formatting.set_approval_handler(handler)
    try:
        result = formatting.prompt_approval("apply registry change")
    finally:
        formatting.set_approval_handler(None)

    assert result is True
    assert captured == ["apply registry change"]


def test_handler_swap_after_import_is_honored():
    """Direct-name imports (the pattern every consumer uses) must hit the swapped handler."""
    from src.utils.formatting import prompt_approval as imported_prompt_approval
    from src.pipeline.phase_bootstrap import prompt_approval as bootstrap_prompt_approval

    seen: list[str] = []
    formatting.set_approval_handler(lambda action: seen.append(action) or False)
    try:
        result_direct = imported_prompt_approval("via test import")
        result_bootstrap = bootstrap_prompt_approval("via bootstrap import")
    finally:
        formatting.set_approval_handler(None)

    assert result_direct is False
    assert result_bootstrap is False
    assert seen == ["via test import", "via bootstrap import"]


def test_clearing_handler_restores_cli_input(monkeypatch):
    formatting.set_approval_handler(lambda _action: True)
    formatting.set_approval_handler(None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    assert formatting.prompt_approval("fall through to input()") is True


def test_handler_return_false_propagates(monkeypatch):
    formatting.set_approval_handler(lambda _action: False)
    try:
        assert formatting.prompt_approval("denied") is False
    finally:
        formatting.set_approval_handler(None)


def test_set_confirm_handler_intercepts_call():
    formatting.set_confirm_handler(lambda question: question == "yes please")
    try:
        assert formatting.prompt_confirm("yes please") is True
        assert formatting.prompt_confirm("nope") is False
    finally:
        formatting.set_confirm_handler(None)


def test_confirm_handler_clears_cleanly(monkeypatch):
    formatting.set_confirm_handler(lambda _q: True)
    formatting.set_confirm_handler(None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")
    assert formatting.prompt_confirm("after clear") is False
