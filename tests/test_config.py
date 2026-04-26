"""Tests for src.config — BenchmarkConfig, ThermalConfig, JSON loading, JSONC, save."""
import json
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConfigDefaults:
    def test_benchmark_defaults(self):
        from src.config import BenchmarkConfig
        b = BenchmarkConfig()
        assert b.cinebench_timeout == 600
        assert b.stress_test_duration == 30

    def test_thermal_defaults(self):
        from src.config import ThermalConfig
        t = ThermalConfig()
        assert t.watchdog_threshold == 95.0
        assert t.watchdog_sustained_secs == 5
        assert t.poll_interval == 1.0


class TestConfigFileLoading:
    def test_missing_config_file_uses_defaults(self, tmp_path, monkeypatch):
        """No lil_bro_config.json -> defaults returned without error."""
        monkeypatch.chdir(tmp_path)
        from src.config import _load_config
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 6000
        assert result.thermal.watchdog_threshold == 95.0

    def test_valid_json_overrides_values(self, tmp_path, monkeypatch):
        """Valid lil_bro_config.json with overrides -> merged correctly."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text(json.dumps({
            "benchmark": {"cinebench_timeout": 300},
            "thermal": {"watchdog_threshold": 85.0},
        }), encoding="utf-8")
        from src.config import _load_config
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 300
        assert result.thermal.watchdog_threshold == 85.0
        # Untouched values keep their defaults
        assert result.benchmark.stress_test_duration == 30
        assert result.thermal.poll_interval == 1.0

    def test_malformed_json_falls_back_to_defaults(self, tmp_path, monkeypatch):
        """Malformed lil_bro_config.json -> silently uses defaults, no crash."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text("{ this is not valid json }", encoding="utf-8")
        from src.config import _load_config
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 600
        assert result.thermal.watchdog_threshold == 95.0

    def test_partial_override_leaves_other_defaults_intact(self, tmp_path, monkeypatch):
        """Only benchmark.cinebench_timeout overridden -> thermal untouched."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text(json.dumps({
            "benchmark": {"cinebench_timeout": 120},
        }), encoding="utf-8")
        from src.config import _load_config
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 120
        assert result.thermal.watchdog_threshold == 95.0

    def test_empty_json_object_uses_defaults(self, tmp_path, monkeypatch):
        """Empty {} config file -> all defaults."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text("{}", encoding="utf-8")
        from src.config import _load_config
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 600

    def test_jsonc_comments_ignored_during_load(self, tmp_path, monkeypatch):
        """JSONC comment lines in config file are silently stripped."""
        monkeypatch.chdir(tmp_path)
        config_file = tmp_path / "lil_bro_config.json"
        config_file.write_text(
            '// This is a comment\n{"benchmark": {"cinebench_timeout": 300}}',
            encoding="utf-8",
        )
        from src.config import _load_config
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 300


class TestStripJsonc:
    def test_removes_comment_lines(self):
        from src.config import _strip_jsonc
        text = '// comment\n{\n  // another\n  "key": 1\n}'
        result = _strip_jsonc(text)
        assert "//" not in result
        data = json.loads(result)
        assert data["key"] == 1

    def test_preserves_urls_in_values(self):
        """// inside JSON string values is not stripped."""
        from src.config import _strip_jsonc
        text = '{"url": "https://example.com"}'
        result = _strip_jsonc(text)
        data = json.loads(result)
        assert data["url"] == "https://example.com"

    def test_preserves_indented_data_lines(self):
        from src.config import _strip_jsonc
        text = '{\n    "a": 1,\n    "b": 2\n}'
        result = _strip_jsonc(text)
        data = json.loads(result)
        assert data == {"a": 1, "b": 2}

    def test_strips_indented_comments(self):
        """Comments with leading whitespace are still stripped."""
        from src.config import _strip_jsonc
        text = '{\n    // indented comment\n    "a": 1\n}'
        result = _strip_jsonc(text)
        assert "//" not in result
        data = json.loads(result)
        assert data["a"] == 1


class TestSaveDefaultConfig:
    def test_creates_file(self, tmp_path, monkeypatch):
        """First run: save_default_config() creates lil_bro_config.json in CWD."""
        monkeypatch.chdir(tmp_path)
        from src.config import save_default_config
        save_default_config()
        config_path = tmp_path / "lil_bro_config.json"
        assert config_path.exists()

    def test_does_not_overwrite(self, tmp_path, monkeypatch):
        """Existing config is never overwritten by save_default_config()."""
        monkeypatch.chdir(tmp_path)
        config_path = tmp_path / "lil_bro_config.json"
        config_path.write_text('{"benchmark": {"cinebench_timeout": 999}}', encoding="utf-8")
        from src.config import save_default_config
        save_default_config()
        content = config_path.read_text(encoding="utf-8")
        assert "999" in content  # Original content preserved

    def test_saved_config_is_loadable(self, tmp_path, monkeypatch):
        """The generated JSONC template is parseable by _load_config()."""
        monkeypatch.chdir(tmp_path)
        from src.config import save_default_config, _load_config
        save_default_config()
        result = _load_config()
        assert result.benchmark.cinebench_timeout == 600
        assert result.benchmark.stress_test_duration == 30
        assert result.thermal.watchdog_threshold == 95.0
        assert result.thermal.poll_interval == 1.0

    def test_survives_readonly_cwd(self, tmp_path, monkeypatch):
        """save_default_config() swallows errors on unreachable path."""
        monkeypatch.chdir(tmp_path)
        from src.config import save_default_config
        with patch("src.config.get_config_path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent_dir" / "lil_bro_config.json"
            save_default_config()  # Should not raise

    def test_template_contains_all_settings(self, tmp_path, monkeypatch):
        """Generated template includes every config key."""
        monkeypatch.chdir(tmp_path)
        from src.config import save_default_config
        save_default_config()
        content = (tmp_path / "lil_bro_config.json").read_text(encoding="utf-8")
        assert "cinebench_timeout" in content
        assert "stress_test_duration" in content
        assert "watchdog_threshold" in content
        assert "watchdog_sustained_secs" in content
        assert "poll_interval" in content


class TestConfigSingleton:
    def test_same_object_on_repeated_imports(self):
        """Module-level config is the same object on repeated imports."""
        import src.config as cfg1
        import src.config as cfg2
        assert cfg1.config is cfg2.config
