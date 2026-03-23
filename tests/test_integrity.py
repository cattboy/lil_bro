import json
import hashlib
import pytest
from unittest.mock import patch, PropertyMock
from pathlib import Path

from src.utils.integrity import verify_integrity, _get_exe_dir


# ── Dev mode (not frozen) ────────────────────────────────────────────────────

def test_dev_mode_skips():
    """In dev mode (not frozen), always returns True."""
    assert verify_integrity() is True


# ── _get_exe_dir ──────────────────────────────────────────────────────────────

def test_get_exe_dir_dev_mode():
    """In dev mode, returns the project root."""
    result = _get_exe_dir()
    # Should be the project root (3 levels up from utils/integrity.py)
    assert result.exists()


@patch("src.utils.integrity.sys")
def test_get_exe_dir_frozen(mock_sys):
    """In frozen mode, returns the directory of the executable."""
    mock_sys.frozen = True
    mock_sys.executable = r"C:\Users\test\dist\lil_bro.exe"
    result = _get_exe_dir()
    assert result == Path(r"C:\Users\test\dist")


# ── Frozen mode — no manifest ────────────────────────────────────────────────

@patch("src.utils.integrity.sys")
def test_frozen_no_manifest(mock_sys, tmp_path):
    """Frozen mode with no integrity.json → skip (return True)."""
    mock_sys.frozen = True
    mock_sys.executable = str(tmp_path / "lil_bro.exe")
    # Create a fake exe but no manifest
    (tmp_path / "lil_bro.exe").write_bytes(b"fake exe")
    assert verify_integrity() is True


# ── Frozen mode — hash matches ───────────────────────────────────────────────

@patch("src.utils.integrity.sys")
def test_frozen_hash_matches(mock_sys, tmp_path):
    """Frozen mode with matching hash → return True."""
    exe_path = tmp_path / "lil_bro.exe"
    exe_path.write_bytes(b"fake exe content")
    expected_hash = hashlib.sha256(b"fake exe content").hexdigest()

    manifest = {"version": "0.1.0", "algorithm": "sha256", "exe_hash": expected_hash}
    (tmp_path / "integrity.json").write_text(json.dumps(manifest))

    mock_sys.frozen = True
    mock_sys.executable = str(exe_path)

    assert verify_integrity() is True


# ── Frozen mode — hash mismatch ──────────────────────────────────────────────

@patch("src.utils.integrity.sys")
def test_frozen_hash_mismatch(mock_sys, tmp_path):
    """Frozen mode with wrong hash → return False and print warning."""
    exe_path = tmp_path / "lil_bro.exe"
    exe_path.write_bytes(b"modified exe content")

    manifest = {"version": "0.1.0", "algorithm": "sha256", "exe_hash": "0" * 64}
    (tmp_path / "integrity.json").write_text(json.dumps(manifest))

    mock_sys.frozen = True
    mock_sys.executable = str(exe_path)

    assert verify_integrity() is False


# ── Frozen mode — corrupted manifest ─────────────────────────────────────────

@patch("src.utils.integrity.sys")
def test_frozen_corrupted_manifest(mock_sys, tmp_path):
    """Frozen mode with unparseable manifest → skip (return True)."""
    exe_path = tmp_path / "lil_bro.exe"
    exe_path.write_bytes(b"fake exe")
    (tmp_path / "integrity.json").write_text("not valid json{{{")

    mock_sys.frozen = True
    mock_sys.executable = str(exe_path)

    assert verify_integrity() is True


# ── Frozen mode — manifest missing exe_hash key ──────────────────────────────

@patch("src.utils.integrity.sys")
def test_frozen_manifest_no_hash_key(mock_sys, tmp_path):
    """Manifest exists but has no exe_hash → skip (return True)."""
    exe_path = tmp_path / "lil_bro.exe"
    exe_path.write_bytes(b"fake exe")
    (tmp_path / "integrity.json").write_text(json.dumps({"version": "0.1.0"}))

    mock_sys.frozen = True
    mock_sys.executable = str(exe_path)

    assert verify_integrity() is True
