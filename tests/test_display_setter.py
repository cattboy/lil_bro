"""Tests for src/agent_tools/display_setter.py -- find_best_mode selection logic."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
from src.agent_tools.display_setter import find_best_mode


class TestFindBestMode:

    def test_find_best_mode_selects_highest_hz_at_native_res(self):
        """When multiple modes exist at native resolution, selects highest Hz."""
        # Mock current mode: 1920x1080 @ 60 Hz
        mock_current = MagicMock()
        mock_current.dmPelsWidth = 1920
        mock_current.dmPelsHeight = 1080
        mock_current.dmDisplayFrequency = 60

        # Available modes: same res at 60, 100, 144 Hz
        mode_60 = MagicMock()
        mode_60.dmPelsWidth = 1920
        mode_60.dmPelsHeight = 1080
        mode_60.dmDisplayFrequency = 60

        mode_100 = MagicMock()
        mode_100.dmPelsWidth = 1920
        mode_100.dmPelsHeight = 1080
        mode_100.dmDisplayFrequency = 100

        mode_144 = MagicMock()
        mode_144.dmPelsWidth = 1920
        mode_144.dmPelsHeight = 1080
        mode_144.dmDisplayFrequency = 144

        with patch("src.agent_tools.display_setter._get_current_mode", return_value=mock_current), \
             patch("src.agent_tools.display_setter.enum_raw_modes", return_value=[mode_60, mode_100, mode_144]):
            result = find_best_mode("DISPLAY1")

        assert result is mode_144

    def test_find_best_mode_prefers_native_resolution(self):
        """When modes at different resolutions available, selects highest Hz at native res."""
        # Mock current mode: 1920x1080 @ 60 Hz
        mock_current = MagicMock()
        mock_current.dmPelsWidth = 1920
        mock_current.dmPelsHeight = 1080
        mock_current.dmDisplayFrequency = 60

        # Available modes: 1920x1080 @ 100 Hz and 2560x1440 @ 144 Hz
        mode_native_100 = MagicMock()
        mode_native_100.dmPelsWidth = 1920
        mode_native_100.dmPelsHeight = 1080
        mode_native_100.dmDisplayFrequency = 100

        mode_other_144 = MagicMock()
        mode_other_144.dmPelsWidth = 2560
        mode_other_144.dmPelsHeight = 1440
        mode_other_144.dmDisplayFrequency = 144

        with patch("src.agent_tools.display_setter._get_current_mode", return_value=mock_current), \
             patch("src.agent_tools.display_setter.enum_raw_modes", return_value=[mode_native_100, mode_other_144]):
            result = find_best_mode("DISPLAY1")

        # Should prefer native res even at lower Hz
        assert result is mode_native_100

    def test_find_best_mode_empty_modes_returns_none(self):
        """When no modes found after filtering, returns None."""
        mock_current = MagicMock()
        mock_current.dmPelsWidth = 1920
        mock_current.dmPelsHeight = 1080
        mock_current.dmDisplayFrequency = 60

        with patch("src.agent_tools.display_setter._get_current_mode", return_value=mock_current), \
             patch("src.agent_tools.display_setter.enum_raw_modes", return_value=[]):
            result = find_best_mode("DISPLAY1")

        assert result is None
