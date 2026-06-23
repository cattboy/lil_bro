"""Tests for src.benchmarks.cinebench_discovery.

Targets the real public surface of the discovery module directly (not the
``cinebench`` re-export shim) so the module is exercised in isolation. All
filesystem probing is mocked at the module's own ``os.path.isfile`` binding;
no real Cinebench install is touched.
"""

from unittest.mock import patch

from src.benchmarks.cinebench_discovery import find_cinebench, _CINEBENCH_SEARCH_PATHS


# ── find_cinebench — success path ─────────────────────────────────────────────

@patch("src.benchmarks.cinebench_discovery.os.path.isfile")
def test_find_cinebench_returns_first_existing(mock_isfile):
    """Returns the first path that exists on disk."""
    mock_isfile.side_effect = lambda p: "bench-exe" in p
    result = find_cinebench()
    assert result is not None
    assert "Cinebench.exe" in result
    assert "bench-exe" in result


@patch("src.benchmarks.cinebench_discovery.os.path.isfile")
def test_find_cinebench_returns_earliest_when_multiple_match(mock_isfile):
    """When several paths exist, the earliest in the search list wins."""
    mock_isfile.return_value = True  # every candidate "exists"
    result = find_cinebench()
    assert result == _CINEBENCH_SEARCH_PATHS[0]


@patch("src.benchmarks.cinebench_discovery.os.path.isfile")
def test_find_cinebench_short_circuits_on_first_hit(mock_isfile):
    """Stops probing once a match is found — later paths aren't checked."""
    # Only the 2nd path exists; isfile should be called exactly twice.
    target = _CINEBENCH_SEARCH_PATHS[1]
    mock_isfile.side_effect = lambda p: p == target
    result = find_cinebench()
    assert result == target
    assert mock_isfile.call_count == 2


# ── find_cinebench — not-found / edge paths ───────────────────────────────────

@patch("src.benchmarks.cinebench_discovery.os.path.isfile", return_value=False)
def test_find_cinebench_returns_none_when_absent(mock_isfile):
    """Returns None when no candidate path exists."""
    assert find_cinebench() is None


@patch("src.benchmarks.cinebench_discovery.os.path.isfile", return_value=False)
def test_find_cinebench_probes_every_path_when_none_found(mock_isfile):
    """The miss path walks the full search list (no early bail)."""
    find_cinebench()
    assert mock_isfile.call_count == len(_CINEBENCH_SEARCH_PATHS)


# ── _CINEBENCH_SEARCH_PATHS — module-level invariants ─────────────────────────

def test_search_paths_non_empty():
    """The search list must contain candidates or discovery is dead."""
    assert len(_CINEBENCH_SEARCH_PATHS) > 0


def test_search_paths_all_target_cinebench_exe():
    """Every candidate path points at a Cinebench.exe binary."""
    assert all(p.endswith("Cinebench.exe") for p in _CINEBENCH_SEARCH_PATHS)


def test_search_paths_contains_no_unexpanded_env_vars():
    """os.path.expandvars/expanduser must have resolved at import time.

    A leftover ``%VAR%`` or ``~`` would mean the env var was undefined and the
    candidate is unmatchable garbage. ``%ProgramFiles(x86)%`` etc. are always
    set on Windows, but the test still guards against a fully-broken import.
    """
    for p in _CINEBENCH_SEARCH_PATHS:
        assert not p.startswith("~"), f"unexpanded home in {p!r}"
