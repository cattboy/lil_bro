from pathlib import Path

from src.utils.paths import (
    get_appdata_dir,
    get_logs_dir,
    get_specs_path,
    get_action_log_path,
)


def test_get_appdata_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = get_appdata_dir()
    assert result == tmp_path / "lil_bro"
    assert result.exists()


def test_get_logs_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = get_logs_dir()
    assert result == tmp_path / "lil_bro" / "logs"
    assert result.exists()


def test_get_specs_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = get_specs_path()
    assert result.name == "full_specs.json"
    assert "lil_bro" in str(result)
    assert "logs" in str(result)


def test_get_action_log_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = get_action_log_path()
    assert result.name == "lil_bro_actions.log"
    assert result == tmp_path / "lil_bro_actions.log"  # CWD root, NOT inside ./lil_bro/


def test_appdata_dir_creates_parents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = get_appdata_dir()
    assert result.exists()


def test_cwd_based_path(tmp_path, monkeypatch):
    """get_appdata_dir() is relative to CWD, not %APPDATA%."""
    monkeypatch.chdir(tmp_path)
    result = get_appdata_dir()
    assert result == Path.cwd() / "lil_bro"
