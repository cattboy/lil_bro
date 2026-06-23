"""Tests for src.benchmarks.cinebench_parser.

``parse_output`` is a pure regex extractor over Cinebench's console log. The
score line shape is ``CB 247.39 (0.00)``; preceding context lines (e.g.
"Running Single CPU Render Test...") label each score. These tests cover the
single/multi/gpu labelling, context-less fallback ordering, and malformed /
empty input.
"""

import pytest

from src.benchmarks.cinebench_parser import parse_output


# ── single-test output ────────────────────────────────────────────────────────

def test_parse_single_cpu_score():
    """A Single CPU context line labels the score CPU_Single."""
    output = "Running Single CPU Render Test...\nCB 247.39 (0.00)\n"
    scores = parse_output(output, full_suite=False)
    assert scores == {"CPU_Single": "247.39 pts"}


def test_parse_multi_cpu_score():
    """A Multi CPU context line labels the score CPU_Multi."""
    output = "Running Multi CPU Render Test...\nCB 15320.11 (0.00)\n"
    scores = parse_output(output, full_suite=False)
    assert scores == {"CPU_Multi": "15320.11 pts"}


def test_parse_gpu_score():
    """A GPU context line labels the score GPU."""
    output = "Running GPU Render Test...\nCB 9876.54 (0.00)\n"
    scores = parse_output(output)
    assert scores == {"GPU": "9876.54 pts"}


# ── full-suite output (multiple scores) ───────────────────────────────────────

def test_parse_full_suite_single_and_multi():
    """Both single and multi scores are extracted from a full-suite run."""
    output = (
        "Running Single CPU Render Test...\nCB 247.39 (0.00)\n"
        "Running Multi CPU Render Test...\nCB 15320.11 (0.00)\n"
    )
    scores = parse_output(output, full_suite=True)
    assert scores["CPU_Single"] == "247.39 pts"
    assert scores["CPU_Multi"] == "15320.11 pts"


def test_parse_recognizes_cpu1_and_cpux_context_tokens():
    """Vendor flag-style context tokens (cpu1 / cpux) also classify scores."""
    output = (
        "g_CinebenchCpu1Test render test\nCB 100.00 (0.00)\n"
        "g_CinebenchCpuXTest render test\nCB 2000.00 (0.00)\n"
    )
    scores = parse_output(output, full_suite=True)
    assert scores["CPU_Single"] == "100.00 pts"
    assert scores["CPU_Multi"] == "2000.00 pts"


# ── context-less fallback ordering ────────────────────────────────────────────

def test_parse_no_context_falls_back_to_single_then_multi():
    """With no labelling context, scores fill CPU_Single then CPU_Multi.

    The 3rd context-less score spills into the generic Score_N slot.
    """
    output = "CB 10.00 (0.00)\nCB 20.00 (0.00)\nCB 30.00 (0.00)\n"
    scores = parse_output(output, full_suite=True)
    assert scores["CPU_Single"] == "10.00 pts"
    assert scores["CPU_Multi"] == "20.00 pts"
    # Third score has nowhere canonical to go -> generic Score_ slot.
    assert any(k.startswith("Score_") and v == "30.00 pts" for k, v in scores.items())


# ── malformed / empty input ───────────────────────────────────────────────────

def test_parse_empty_string_returns_empty_dict():
    assert parse_output("") == {}


def test_parse_no_score_lines_returns_empty_dict():
    assert parse_output("just some log noise\nnothing useful here\n") == {}


@pytest.mark.parametrize(
    "bad_line",
    [
        "CB no-number (0.00)",      # non-numeric score
        "CBX 247.39 (0.00)",        # wrong prefix (CBX, not CB+space)
        "247.39 CB (0.00)",         # score before CB token
        "CB 247.39",                # missing the (deviation) group
        "  CB247.39 (0.00)",        # no space after CB
    ],
)
def test_parse_ignores_malformed_score_lines(bad_line):
    """Lines that don't match the strict ``CB <num> (<num>)`` shape are skipped."""
    assert parse_output(bad_line + "\n") == {}


def test_parse_tolerates_whitespace_and_blank_lines():
    """Indented score lines and interspersed blanks still parse."""
    output = (
        "\n   Running Single CPU Render Test...   \n\n"
        "   CB 333.33 (0.00)   \n\n"
    )
    scores = parse_output(output, full_suite=False)
    assert scores == {"CPU_Single": "333.33 pts"}
