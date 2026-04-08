"""
lil_bro runtime configuration.

Defaults are defined as dataclass fields. An optional ``lil_bro_config.json``
placed next to the .exe (or project root in dev) can override any value.

Example lil_bro_config.json:
    {
        "benchmark": {"cinebench_timeout": 300},
        "thermal": {"watchdog_threshold": 90.0}
    }

Values not present in the file fall back to defaults. Missing or malformed
files are silently ignored — lil_bro always starts with working defaults.
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path


def _get_exe_dir() -> Path:
    """Return the directory containing the .exe (frozen) or project root (dev)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent


@dataclass
class BenchmarkConfig:
    cinebench_timeout: int = 600      # seconds before Cinebench run is aborted
    stress_test_duration: int = 30    # seconds for CPU stress fallback


@dataclass
class ThermalConfig:
    watchdog_threshold: float = 95.0  # °C — abort benchmark if held above this
    poll_interval: float = 1.0        # seconds between LHM temperature samples


@dataclass
class AppConfig:
    benchmark: BenchmarkConfig
    thermal: ThermalConfig


def _load_config() -> AppConfig:
    """Load config from lil_bro_config.json if present, else return defaults."""
    benchmark = BenchmarkConfig()
    thermal = ThermalConfig()

    config_path = _get_exe_dir() / "lil_bro_config.json"
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                b = data.get("benchmark", {})
                if isinstance(b, dict):
                    if "cinebench_timeout" in b:
                        benchmark.cinebench_timeout = int(b["cinebench_timeout"])
                    if "stress_test_duration" in b:
                        benchmark.stress_test_duration = int(b["stress_test_duration"])
                t = data.get("thermal", {})
                if isinstance(t, dict):
                    if "watchdog_threshold" in t:
                        thermal.watchdog_threshold = float(t["watchdog_threshold"])
                    if "poll_interval" in t:
                        thermal.poll_interval = float(t["poll_interval"])
        except Exception:
            pass  # Malformed config — silently use defaults

    return AppConfig(benchmark=benchmark, thermal=thermal)


# Module-level singleton — loaded once at first import.
config: AppConfig = _load_config()
