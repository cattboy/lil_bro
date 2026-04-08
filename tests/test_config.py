"""Tests for src.config — BenchmarkConfig, ThermalConfig, JSON loading."""
import importlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConfigDefaults:
    def test_benchmark_defaults(self):
        from src.config import config
        assert config.benchmark.cinebench_timeout == 600
        assert config.benchmark.stress_test_duration == 30

    def test_thermal_defaults(self):
        from src.config import config
        assert config.thermal.watchdog_threshold == 95.0
        assert config.thermal.poll_interval == 1.0


class TestConfigFileLoading:
    def test_missing_config_file_uses_defaults(self, tmp_path):
        """No lil_bro_config.json → defaults returned without error."""
        with patch("src.config._get_exe_dir", return_value=tmp_path):
            import src.config as cfg_module
            result = cfg_module._load_config()
        assert result.benchmark.cinebench_timeout == 600
        assert result.thermal.watchdog_threshold == 95.0

    def test_valid_json_overrides_values(self, tmp_path):
        """Valid lil_bro_config.json with overrides → merged correctly."""
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text(json.dumps({
            "benchmark": {"cinebench_timeout": 300},
            "thermal": {"watchdog_threshold": 85.0},
        }), encoding="utf-8")
        with patch("src.config._get_exe_dir", return_value=tmp_path):
            import src.config as cfg_module
            result = cfg_module._load_config()
        assert result.benchmark.cinebench_timeout == 300
        assert result.thermal.watchdog_threshold == 85.0
        # Untouched values keep their defaults
        assert result.benchmark.stress_test_duration == 30
        assert result.thermal.poll_interval == 1.0

    def test_malformed_json_falls_back_to_defaults(self, tmp_path):
        """Malformed lil_bro_config.json → silently uses defaults, no crash."""
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text("{ this is not valid json }", encoding="utf-8")
        with patch("src.config._get_exe_dir", return_value=tmp_path):
            import src.config as cfg_module
            result = cfg_module._load_config()
        assert result.benchmark.cinebench_timeout == 600
        assert result.thermal.watchdog_threshold == 95.0

    def test_partial_override_leaves_other_defaults_intact(self, tmp_path):
        """Only benchmark.cinebench_timeout overridden → thermal untouched."""
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text(json.dumps({
            "benchmark": {"cinebench_timeout": 120},
        }), encoding="utf-8")
        with patch("src.config._get_exe_dir", return_value=tmp_path):
            import src.config as cfg_module
            result = cfg_module._load_config()
        assert result.benchmark.cinebench_timeout == 120
        assert result.thermal.watchdog_threshold == 95.0

    def test_empty_json_object_uses_defaults(self, tmp_path):
        """Empty {} config file → all defaults."""
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text("{}", encoding="utf-8")
        with patch("src.config._get_exe_dir", return_value=tmp_path):
            import src.config as cfg_module
            result = cfg_module._load_config()
        assert result.benchmark.cinebench_timeout == 600
