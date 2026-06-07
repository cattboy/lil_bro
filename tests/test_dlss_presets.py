"""Tests for the DLSS preset policy service (src/utils/dlss_presets.py).

Covers classify() tiering, get_preset() resolution + the invalid-priority guard,
the DLSS_VALUE_BY_LETTER reverse map, monitor_aware_priority (E2), the
resolve_startup_priority precedence chain, and config.nvidia.dlss.priority parsing.
"""
from __future__ import annotations

import pytest

from src.utils.dlss_presets import (
    classify,
    get_preset,
    monitor_aware_priority,
    resolve_startup_priority,
)
from src.utils.nvidia_npi import DLSS_LETTER_MAP, DLSS_VALUE_BY_LETTER


class TestClassify:
    @pytest.mark.parametrize("name,expected", [
        ("NVIDIA GeForce RTX 5090", "fp8"),
        ("NVIDIA GeForce RTX 4060", "fp8"),
        ("NVIDIA GeForce RTX 3080", "no_fp8"),
        ("NVIDIA GeForce RTX 2070 Super", "no_fp8"),
        ("NVIDIA GeForce GTX 1080", "unsupported"),
        ("NVIDIA RTX 2000 Ada Generation", "unsupported"),
        ("NVIDIA RTX A6000", "unsupported"),
        ("AMD Radeon RX 7900 XTX", "unknown"),
        ("NVIDIA GeForce RTX 6090", "unknown"),   # future gen not in table
        ("", "unknown"),
    ])
    def test_classify(self, name, expected):
        assert classify(name) == expected


class TestGetPreset:
    @pytest.mark.parametrize("name,priority,letter,value", [
        ("NVIDIA GeForce RTX 5090", "quality", "M", 13),
        ("NVIDIA GeForce RTX 4090", "fps", "L", 12),
        ("NVIDIA GeForce RTX 3080", "quality", "K", 11),
        ("NVIDIA GeForce RTX 3080", "fps", "K", 11),
        ("NVIDIA GeForce RTX 2070", "quality", "K", 11),
    ])
    def test_get_preset_letters(self, name, priority, letter, value):
        preset = get_preset(name, priority)
        assert preset is not None
        assert preset.letter == letter
        assert preset.value == value

    @pytest.mark.parametrize("name", [
        "NVIDIA GeForce GTX 1080",
        "NVIDIA RTX 2000 Ada Generation",
        "AMD Radeon RX 7900 XTX",
        "",
    ])
    def test_get_preset_none_for_unsupported(self, name):
        assert get_preset(name, "quality") is None

    def test_invalid_priority_falls_back_to_quality(self):
        preset = get_preset("NVIDIA GeForce RTX 5090", "garbage")
        assert preset is not None
        assert preset.letter == "M"          # quality fallback, never KeyError
        assert preset.priority == "quality"

    def test_priority_none_reads_config(self, monkeypatch):
        from src.config import config
        monkeypatch.setattr(config.nvidia.dlss, "priority", "fps")
        assert get_preset("NVIDIA GeForce RTX 4090").letter == "L"
        monkeypatch.setattr(config.nvidia.dlss, "priority", "quality")
        assert get_preset("NVIDIA GeForce RTX 4090").letter == "M"


class TestValueByLetter:
    def test_roundtrip(self):
        assert DLSS_VALUE_BY_LETTER["K"] == 11
        assert DLSS_VALUE_BY_LETTER["L"] == 12
        assert DLSS_VALUE_BY_LETTER["M"] == 13
        for letter in ("K", "L", "M"):
            assert DLSS_LETTER_MAP[DLSS_VALUE_BY_LETTER[letter]] == letter


class TestMonitorAwarePriority:
    @pytest.mark.parametrize("display,expected", [
        ({"max_refresh_hz": 60, "at_resolution": "1920x1080"}, "quality"),   # 60Hz cap
        ({"max_refresh_hz": 144, "at_resolution": "3840x2160"}, "quality"),  # 4K
        ({"max_refresh_hz": 240, "at_resolution": "2560x1440"}, None),       # 1440p high-refresh
        ({"max_refresh_hz": 165, "at_resolution": "1920x1080"}, None),       # 1080p high-refresh
        ({"current_refresh_hz": 60, "at_resolution": ""}, "quality"),        # 60Hz, no res
        ({}, None),
        (None, None),
        ({"error": "no displays"}, None),
    ])
    def test_monitor_aware(self, display, expected):
        assert monitor_aware_priority(display) == expected


class TestResolveStartupPriority:
    def test_manual_wins_over_monitor(self):
        specs = {"DisplayCapabilities": [{"max_refresh_hz": 60, "at_resolution": "1920x1080"}]}
        # 60Hz monitor would pick quality, but a stored manual "fps" must win.
        assert resolve_startup_priority(specs, "fps") == "fps"

    def test_monitor_aware_when_no_manual(self):
        specs = {"DisplayCapabilities": [{"max_refresh_hz": 60, "at_resolution": "1920x1080"}]}
        assert resolve_startup_priority(specs, None) == "quality"

    def test_falls_to_config_when_monitor_neutral(self, monkeypatch):
        from src.config import config
        monkeypatch.setattr(config.nvidia.dlss, "priority", "fps")
        specs = {"DisplayCapabilities": [{"max_refresh_hz": 240, "at_resolution": "2560x1440"}]}
        # 1440p high-refresh -> monitor None -> config default ("fps" here).
        assert resolve_startup_priority(specs, None) == "fps"

    def test_no_displays_falls_to_config(self, monkeypatch):
        from src.config import config
        monkeypatch.setattr(config.nvidia.dlss, "priority", "quality")
        assert resolve_startup_priority({}, None) == "quality"


class TestConfigPriorityParsing:
    def _load_with(self, tmp_path, monkeypatch, body: str):
        from src import config as cfgmod
        cfg_file = tmp_path / "lil_bro_config.json"
        cfg_file.write_text(body, encoding="utf-8")
        monkeypatch.setattr(cfgmod, "get_config_path", lambda: cfg_file)
        return cfgmod._load_config()

    def test_valid_fps(self, tmp_path, monkeypatch):
        loaded = self._load_with(tmp_path, monkeypatch, '{"nvidia":{"dlss":{"priority":"fps"}}}')
        assert loaded.nvidia.dlss.priority == "fps"

    def test_invalid_defaults_quality(self, tmp_path, monkeypatch):
        loaded = self._load_with(tmp_path, monkeypatch, '{"nvidia":{"dlss":{"priority":"bogus"}}}')
        assert loaded.nvidia.dlss.priority == "quality"

    def test_missing_nvidia_defaults_quality(self, tmp_path, monkeypatch):
        loaded = self._load_with(tmp_path, monkeypatch, '{"benchmark":{"cinebench_timeout":300}}')
        assert loaded.nvidia.dlss.priority == "quality"

    def test_template_contains_dlss_priority(self):
        from src.config import _DEFAULT_CONFIG_TEMPLATE
        assert '"dlss"' in _DEFAULT_CONFIG_TEMPLATE
        assert '"priority": "quality"' in _DEFAULT_CONFIG_TEMPLATE
