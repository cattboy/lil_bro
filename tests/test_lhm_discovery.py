"""Tests for src.collectors.sub.lhm_discovery.

find_lhm_executable() walks a fixed list of candidate paths and returns the first
that exists, plus a flag marking whether it's the custom lhm-server.exe (vs the
full LibreHardwareMonitor.exe). Pure os.path.isfile probing — patched here so no
real filesystem layout is required.
"""

import os
from unittest.mock import patch

import pytest

from src.collectors.sub.lhm_discovery import (
    _LHM_SEARCH_PATHS,
    _PROJECT_ROOT,
    find_lhm_executable,
)


def test_search_paths_constant_shape():
    """The search list is non-empty and prefers the custom server first."""
    assert isinstance(_LHM_SEARCH_PATHS, list)
    assert len(_LHM_SEARCH_PATHS) >= 4
    # First candidate must be the custom minimal server (checked before full LHM).
    assert os.path.basename(_LHM_SEARCH_PATHS[0]) == "lhm-server.exe"
    # Full LibreHardwareMonitor must also appear somewhere as a fallback.
    assert any("LibreHardwareMonitor.exe" in p for p in _LHM_SEARCH_PATHS)


def test_project_root_is_absolute():
    """_PROJECT_ROOT resolves to an absolute path (three levels above the module)."""
    assert os.path.isabs(_PROJECT_ROOT)


def test_find_returns_custom_server_first():
    """lhm-server.exe present → (path, is_custom=True)."""
    with patch(
        "src.collectors.sub.lhm_discovery.os.path.isfile",
        side_effect=lambda p: p.endswith("lhm-server.exe"),
    ):
        path, is_custom = find_lhm_executable()

    assert path is not None
    assert path.endswith("lhm-server.exe")
    assert is_custom is True


def test_find_returns_full_lhm_when_only_that_exists():
    """Only full LibreHardwareMonitor.exe present → (path, is_custom=False)."""
    with patch(
        "src.collectors.sub.lhm_discovery.os.path.isfile",
        side_effect=lambda p: "LibreHardwareMonitor.exe" in p and "lhm-server" not in p,
    ):
        path, is_custom = find_lhm_executable()

    assert path is not None
    assert "LibreHardwareMonitor.exe" in path
    assert is_custom is False


def test_find_prefers_custom_over_full_when_both_present():
    """Both binaries present → custom server wins (it's earlier in the search order)."""
    with patch("src.collectors.sub.lhm_discovery.os.path.isfile", return_value=True):
        path, is_custom = find_lhm_executable()

    # return_value=True makes every probe succeed; first path is the custom server.
    assert path == _LHM_SEARCH_PATHS[0]
    assert is_custom is True


def test_find_returns_none_when_nothing_found():
    """No candidate exists → (None, False)."""
    with patch("src.collectors.sub.lhm_discovery.os.path.isfile", return_value=False):
        path, is_custom = find_lhm_executable()

    assert path is None
    assert is_custom is False
