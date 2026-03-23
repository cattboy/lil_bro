import os
import pytest
from unittest.mock import patch
from pathlib import Path

from src.utils.paths import (
    get_appdata_dir,
    get_logs_dir,
    get_specs_path,
    get_action_log_path,
)


@patch.dict(os.environ, {"APPDATA": "/tmp/fake_appdata"})
def test_get_appdata_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = get_appdata_dir()
    assert result == tmp_path / "lil_bro"
    assert result.exists()


@patch.dict(os.environ, {"APPDATA": "/tmp/fake_appdata"})
def test_get_logs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = get_logs_dir()
    assert result == tmp_path / "lil_bro" / "logs"
    assert result.exists()


@patch.dict(os.environ, {"APPDATA": "/tmp/fake_appdata"})
def test_get_specs_path(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = get_specs_path()
    assert result.name == "full_specs.json"
    assert "lil_bro" in str(result)
    assert "logs" in str(result)


@patch.dict(os.environ, {"APPDATA": "/tmp/fake_appdata"})
def test_get_action_log_path(tmp_path, monkeypatch):
    monkeypatch.setenv("APPDATA", str(tmp_path))
    result = get_action_log_path()
    assert result.name == "lil_bro_actions.log"
    assert "lil_bro" in str(result)


def test_appdata_dir_creates_parents(tmp_path, monkeypatch):
    deep = tmp_path / "nested" / "deep"
    monkeypatch.setenv("APPDATA", str(deep))
    result = get_appdata_dir()
    assert result.exists()


def test_fallback_when_no_appdata_env(tmp_path, monkeypatch):
    """When APPDATA is not set, falls back to Path.home() / AppData / Roaming."""
    monkeypatch.delenv("APPDATA", raising=False)
    result = get_appdata_dir()
    assert "lil_bro" in str(result)
