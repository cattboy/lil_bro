"""
Tests for src/llm/model_loader.py.

No real model is downloaded or loaded — llama_cpp is not installed in the dev
venv, and the download path (urllib) is never invoked. We patch the import
boundary (sys.modules["llama_cpp"]), the download prompt, and the filesystem.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import src.llm.model_loader as model_loader
from src.llm.model_loader import (
    MODEL_FILENAME,
    get_model_path,
    get_model_status,
    load_model,
)


# ── get_model_path ────────────────────────────────────────────────────────────


def test_get_model_path_uses_appdata(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\fake\appdata")
    result = get_model_path()
    assert result == Path(r"C:\fake\appdata") / "lil_bro" / "models" / MODEL_FILENAME


def test_get_model_path_ends_in_expected_filename(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\fake\appdata")
    result = get_model_path()
    assert result.name == "Qwen2.5-Coder-7B-Instruct.Q4_K_M.gguf"
    assert result.parent.name == "models"
    assert result.parent.parent.name == "lil_bro"


def test_get_model_path_falls_back_to_home_when_appdata_unset(monkeypatch):
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(Path, "home", lambda: Path(r"C:\users\someone"))
    result = get_model_path()
    expected = (
        Path(r"C:\users\someone")
        / "AppData"
        / "Roaming"
        / "lil_bro"
        / "models"
        / MODEL_FILENAME
    )
    assert result == expected


def test_get_model_path_falls_back_when_appdata_empty(monkeypatch):
    # Empty string is falsy → `os.environ.get(...) or <home fallback>` takes home.
    monkeypatch.setenv("APPDATA", "")
    monkeypatch.setattr(Path, "home", lambda: Path(r"C:\users\someone"))
    result = get_model_path()
    assert str(result).startswith(str(Path(r"C:\users\someone") / "AppData" / "Roaming"))


# ── get_model_status ──────────────────────────────────────────────────────────


def test_get_model_status_llama_absent(monkeypatch):
    # Ensure llama_cpp resolves as not-importable for this test.
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    monkeypatch.setenv("APPDATA", r"C:\fake\appdata")
    status = get_model_status()
    assert status["llama_installed"] is False


def test_get_model_status_llama_present(monkeypatch):
    monkeypatch.setitem(sys.modules, "llama_cpp", MagicMock())
    monkeypatch.setenv("APPDATA", r"C:\fake\appdata")
    status = get_model_status()
    assert status["llama_installed"] is True


def test_get_model_status_model_downloaded_true(monkeypatch, tmp_path):
    model_path = tmp_path / "model.gguf"
    model_path.write_bytes(b"fake")
    monkeypatch.setattr(model_loader, "get_model_path", lambda: model_path)
    status = get_model_status()
    assert status["model_downloaded"] is True
    assert status["model_path"] == str(model_path)


def test_get_model_status_model_downloaded_false(monkeypatch, tmp_path):
    model_path = tmp_path / "missing.gguf"
    monkeypatch.setattr(model_loader, "get_model_path", lambda: model_path)
    status = get_model_status()
    assert status["model_downloaded"] is False


def test_get_model_status_keys(monkeypatch):
    monkeypatch.setenv("APPDATA", r"C:\fake\appdata")
    status = get_model_status()
    assert set(status) == {"llama_installed", "model_downloaded", "model_path"}


# ── load_model ────────────────────────────────────────────────────────────────


def test_load_model_returns_none_when_llama_missing(monkeypatch):
    # Force the `from llama_cpp import Llama` to raise ImportError.
    monkeypatch.setitem(sys.modules, "llama_cpp", None)
    assert load_model() is None


def test_load_model_returns_none_when_download_declined(monkeypatch, tmp_path):
    # llama_cpp present, but the model file does not exist and user declines.
    fake_llama = MagicMock()
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama)
    missing = tmp_path / "missing.gguf"
    monkeypatch.setattr(model_loader, "get_model_path", lambda: missing)
    monkeypatch.setattr(model_loader, "prompt_confirm", lambda *a, **k: False)

    download_called = {"hit": False}

    def _no_download(dest):
        download_called["hit"] = True
        return True

    monkeypatch.setattr(model_loader, "_download_model", _no_download)

    assert load_model() is None
    assert download_called["hit"] is False  # declined before download


def test_load_model_returns_none_when_download_fails(monkeypatch, tmp_path):
    fake_llama = MagicMock()
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_llama)
    missing = tmp_path / "missing.gguf"
    monkeypatch.setattr(model_loader, "get_model_path", lambda: missing)
    monkeypatch.setattr(model_loader, "prompt_confirm", lambda *a, **k: True)
    monkeypatch.setattr(model_loader, "_download_model", lambda dest: False)

    assert load_model() is None


def test_load_model_loads_existing_cached_model(monkeypatch, tmp_path):
    # Model already cached → no prompt, no download, Llama constructed.
    cached = tmp_path / "cached.gguf"
    cached.write_bytes(b"fake")

    constructed = {}

    class FakeLlama:
        def __init__(self, **kwargs):
            constructed.update(kwargs)

    fake_module = MagicMock()
    fake_module.Llama = FakeLlama
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)
    monkeypatch.setattr(model_loader, "get_model_path", lambda: cached)

    def _should_not_prompt(*a, **k):
        raise AssertionError("prompt_confirm called for an already-cached model")

    monkeypatch.setattr(model_loader, "prompt_confirm", _should_not_prompt)

    llm = load_model()
    assert isinstance(llm, FakeLlama)
    assert constructed["model_path"] == str(cached)
    assert constructed["n_gpu_layers"] == 0  # CPU-only invariant
    assert constructed["n_ctx"] == 2048


def test_load_model_returns_none_on_load_exception(monkeypatch, tmp_path):
    cached = tmp_path / "cached.gguf"
    cached.write_bytes(b"fake")

    def _boom(**kwargs):
        raise RuntimeError("corrupt gguf")

    fake_module = MagicMock()
    fake_module.Llama = _boom
    monkeypatch.setitem(sys.modules, "llama_cpp", fake_module)
    monkeypatch.setattr(model_loader, "get_model_path", lambda: cached)

    assert load_model() is None
