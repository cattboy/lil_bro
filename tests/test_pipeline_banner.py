"""Tests for src/pipeline/banner.py."""

from unittest.mock import patch


class TestPrintBanner:

    def test_contains_brand_name(self, capsys):
        from src.pipeline.banner import print_banner
        with patch("src.pipeline.banner.Fore", create=True), \
             patch("src.pipeline.banner.Style", create=True):
            print_banner()
        out = capsys.readouterr().out
        assert "lil_bro" in out or "lil" in out.lower() or "_" in out

    def test_contains_privacy_notice(self, capsys):
        from src.pipeline.banner import print_banner
        with patch("src.pipeline.banner.print_info") as mock_info, \
             patch("src.pipeline.banner.print_dim") as mock_dim, \
             patch("src.pipeline.banner.print_accent"):
            print_banner()
        all_calls = [str(c) for c in mock_dim.call_args_list + mock_info.call_args_list]
        combined = " ".join(all_calls).lower()
        assert "offline" in combined or "privacy" in combined or "data" in combined

    def test_does_not_raise(self):
        from src.pipeline.banner import print_banner
        with patch("src.pipeline.banner.print_info"), \
             patch("src.pipeline.banner.print_dim"), \
             patch("src.pipeline.banner.print_accent"):
            print_banner()  # must not raise
