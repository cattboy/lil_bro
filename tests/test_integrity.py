"""
Tests for src/utils/integrity.py.

`verify_integrity` is currently a download-source reminder, not a hash check:
it always returns True and only emits the official-release-page notice when
NOT in silent-pass mode. Tests assert both the return contract and the
conditional output (captured via capsys).
"""
import pytest

from src.utils.integrity import verify_integrity

OFFICIAL_URL = "https://github.com/cattboy/lil_bro/releases"


def test_returns_true_by_default():
    assert verify_integrity() is True


@pytest.mark.parametrize("silent_pass", [True, False, None])
def test_always_returns_true(silent_pass):
    # Truthy and falsy silent_pass values all pass — it never hard-fails.
    assert verify_integrity(silent_pass=silent_pass) is True


def test_silent_pass_emits_nothing(capsys):
    verify_integrity(silent_pass=True)
    out = capsys.readouterr().out
    assert out == ""


def test_non_silent_prints_official_release_url(capsys):
    result = verify_integrity(silent_pass=False)
    out = capsys.readouterr().out
    assert result is True
    assert OFFICIAL_URL in out
    assert "should only be downloaded" in out


def test_default_is_silent(capsys):
    # Default arg is silent_pass=True → no notice printed.
    verify_integrity()
    assert capsys.readouterr().out == ""
