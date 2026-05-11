"""Verifies the T-001 sink override on every print_* helper.

Two paths must both work:

1. Per-call ``output_sink=...`` parameter — used inside specific contexts
   (e.g. an output-panel widget that wants to capture one phase's output).
2. Module-level default sink installed via ``set_default_sink()`` — used by
   the GUI bridge at startup so every existing call site streams to the
   panel without having to thread a sink argument through every layer.
"""

from __future__ import annotations

import io
from contextlib import redirect_stdout

import pytest

from src.utils import formatting


PRINT_FUNCS = [
    ("print_header", ("Title",)),
    ("print_success", ("ok",)),
    ("print_warning", ("careful",)),
    ("print_error", ("oops",)),
    ("print_info", ("note",)),
    ("print_step", ("doing thing",)),
    ("print_step_done", ()),
    ("print_dim", ("muted",)),
    ("print_accent", ("accent",)),
    ("print_prompt", ("> ",)),
    ("print_key_value", ("CPU", "Ryzen")),
    ("print_section_divider", ("Section",)),
    ("print_audit_summary", (3, 1, 0)),
    ("print_finding", ("CPU", "ok", "OK")),
    ("print_proposal", (1, "HIGH", "title", "explain", "do thing", True)),
]


@pytest.mark.parametrize("fn_name, args", PRINT_FUNCS)
def test_per_call_sink_captures_output(fn_name, args):
    captured: list[str] = []
    fn = getattr(formatting, fn_name)
    fn(*args, output_sink=captured.append)
    assert captured, f"{fn_name} produced no output"
    assert all(isinstance(s, str) for s in captured)


@pytest.mark.parametrize("fn_name, args", PRINT_FUNCS)
def test_default_sink_captures_output(fn_name, args):
    captured: list[str] = []
    formatting.set_default_sink(captured.append)
    try:
        getattr(formatting, fn_name)(*args)
    finally:
        formatting.set_default_sink(None)
    assert captured


@pytest.mark.parametrize("fn_name, args", PRINT_FUNCS)
def test_no_sink_falls_back_to_print(fn_name, args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        getattr(formatting, fn_name)(*args)
    assert buf.getvalue(), f"{fn_name} did not write to stdout in CLI mode"


def test_per_call_sink_overrides_default_sink():
    default: list[str] = []
    per_call: list[str] = []
    formatting.set_default_sink(default.append)
    try:
        formatting.print_info("hello", output_sink=per_call.append)
    finally:
        formatting.set_default_sink(None)
    assert per_call and not default


def test_set_default_sink_clears_to_none():
    captured: list[str] = []
    formatting.set_default_sink(captured.append)
    formatting.set_default_sink(None)
    buf = io.StringIO()
    with redirect_stdout(buf):
        formatting.print_info("after clear")
    assert not captured
    assert buf.getvalue()
