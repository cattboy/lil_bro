"""REGRESSION GUARD — importing the GUI must not pollute the CLI handlers.

The T-001 sink refactor made every print_* go through ``_DEFAULT_SINK``
when it's set. The handler-registry refactor likewise routes
``prompt_approval`` / ``prompt_confirm`` through ``_APPROVAL_HANDLER`` /
``_CONFIRM_HANDLER`` when set. If the GUI bridge accidentally installs
itself at import time (instead of explicit ``install()`` from
``app.run``), every CLI invocation would silently route through Qt
sinks that aren't wired — output disappears, prompts hang.

This guard imports the entire GUI surface and asserts none of the
registries got touched. CLI-mode call sites (``lil_bro.exe --terminal``)
must keep working byte-equivalent to today.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

from src.utils import formatting, progress_bar


def test_gui_imports_do_not_install_sinks_or_handlers():
    # Ensure clean state.
    formatting.set_default_sink(None)
    formatting.set_approval_handler(None)
    formatting.set_confirm_handler(None)
    progress_bar.set_progress_sink(None)

    # Import the entire GUI module surface — none of these should
    # call set_*_sink / set_*_handler at import time.
    import src.gui.app  # noqa: F401
    import src.gui.bridge  # noqa: F401
    import src.gui.signals  # noqa: F401
    import src.gui.startup  # noqa: F401
    import src.gui.theme  # noqa: F401
    import src.gui.worker  # noqa: F401
    import src.gui.widgets.approval_dialog  # noqa: F401
    import src.gui.widgets.batch_selection_dialog  # noqa: F401
    import src.gui.widgets.confirm_dialog  # noqa: F401
    import src.gui.widgets.output_panel  # noqa: F401
    import src.gui.widgets.phase_card  # noqa: F401
    import src.gui.widgets.splash  # noqa: F401
    import src.gui.windows.main_window  # noqa: F401

    assert formatting._DEFAULT_SINK is None
    assert formatting._APPROVAL_HANDLER is None
    assert formatting._CONFIRM_HANDLER is None
    assert progress_bar._PROGRESS_SINK is None


def test_cli_print_helpers_still_write_to_stdout():
    """With no GUI bridge installed, every print_* must reach stdout."""
    formatting.set_default_sink(None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        formatting.print_info("CLI line 1")
        formatting.print_success("CLI line 2")
        formatting.print_error("CLI line 3")
    output = buf.getvalue()
    assert "CLI line 1" in output
    assert "CLI line 2" in output
    assert "CLI line 3" in output


def test_cli_prompt_approval_uses_input(monkeypatch):
    formatting.set_approval_handler(None)
    answers = iter(["y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    assert formatting.prompt_approval("CLI approval question") is True


def test_cli_prompt_confirm_uses_input(monkeypatch):
    formatting.set_confirm_handler(None)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "n")
    assert formatting.prompt_confirm("CLI confirm question") is False
