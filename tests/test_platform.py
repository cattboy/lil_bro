"""Tests for src/utils/platform.py."""

from unittest.mock import patch


class TestIsWindows:

    def test_is_bool(self):
        from src.utils.platform import IS_WINDOWS
        assert isinstance(IS_WINDOWS, bool)


class TestIsAdmin:

    def test_returns_false_when_not_windows(self):
        with patch("src.utils.platform.IS_WINDOWS", False):
            from src.utils import platform as p
            # Re-evaluate with patched IS_WINDOWS
            result = p.is_admin()
        assert result is False

    def test_returns_true_when_ctypes_returns_nonzero(self):
        with patch("src.utils.platform.IS_WINDOWS", True), \
             patch("src.utils.platform.ctypes.windll.shell32.IsUserAnAdmin", return_value=1):
            from src.utils import platform as p
            assert p.is_admin() is True

    def test_returns_false_when_ctypes_raises(self):
        with patch("src.utils.platform.IS_WINDOWS", True), \
             patch("src.utils.platform.ctypes.windll.shell32.IsUserAnAdmin",
                   side_effect=OSError("no windll")):
            from src.utils import platform as p
            assert p.is_admin() is False
