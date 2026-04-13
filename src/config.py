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
from dataclasses import dataclass
from pathlib import Path


def get_config_path() -> Path:
    """Return the path to lil_bro_config.json (CWD root)."""
    return Path.cwd() / "lil_bro_config.json"


def _strip_jsonc(text: str) -> str:
    """Strip ``//`` comment lines from JSONC text, returning valid JSON.

    Only strips lines where ``//`` is the first non-whitespace token.
    This avoids false positives on URLs or strings containing ``//``.
    """
    lines = []
    for line in text.splitlines():
        if not line.lstrip().startswith("//"):
            lines.append(line)
    return "\n".join(lines)


@dataclass
class BenchmarkConfig:
    cinebench_timeout: int = 600      # seconds before Cinebench run is aborted
    stress_test_duration: int = 30    # seconds for CPU stress fallback


@dataclass
class ThermalConfig:
    watchdog_threshold: float = 95.0  # °C — abort benchmark if held above this
    watchdog_sustained_secs: int = 5  # consecutive seconds over threshold before abort
    poll_interval: float = 1.0        # seconds between LHM temperature samples


@dataclass
class AppConfig:
    benchmark: BenchmarkConfig
    thermal: ThermalConfig


def _load_config() -> AppConfig:
    """Load config from lil_bro_config.json if present, else return defaults."""
    benchmark = BenchmarkConfig()
    thermal = ThermalConfig()

    config_path = get_config_path()
    if config_path.exists():
        try:
            raw = config_path.read_text(encoding="utf-8")
            data = json.loads(_strip_jsonc(raw))
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
                    if "watchdog_sustained_secs" in t:
                        thermal.watchdog_sustained_secs = int(t["watchdog_sustained_secs"])
                    if "poll_interval" in t:
                        thermal.poll_interval = float(t["poll_interval"])
        except Exception:
            pass  # Malformed config — silently use defaults

    return AppConfig(benchmark=benchmark, thermal=thermal)


# Module-level singleton — loaded once at first import.
config: AppConfig = _load_config()


_DEFAULT_CONFIG_TEMPLATE = """\
// lil_bro configuration file
// Edit values below to customize behavior. Delete this file to reset to defaults.
// Lines starting with // are comments and are ignored.
{
    // ── Benchmark Settings ──────────────────────────────────────────

    "benchmark": {
        // Maximum seconds to wait for a Cinebench run before aborting.
        "cinebench_timeout": 600,

        // Duration (seconds) for the CPU stress-test fallback
        // (used when Cinebench is unavailable).
        "stress_test_duration": 30
    },

    // ── Thermal Settings ────────────────────────────────────────────

    "thermal": {
        // Temperature ceiling in °C. Benchmarks abort if held above this.
        "watchdog_threshold": 95.0,

        // Consecutive seconds a component must stay above the threshold
        // before the benchmark is aborted. Higher = more tolerant of spikes.
        "watchdog_sustained_secs": 5,

        // Seconds between LibreHardwareMonitor temperature polls.
        "poll_interval": 1.0
    }
}
"""


def save_default_config() -> None:
    """Write the default config template to CWD if it does not already exist.

    Safe to call multiple times — the file is never overwritten.
    All exceptions are swallowed so this never masks a real error.
    """
    config_path = get_config_path()
    if config_path.exists():
        return
    try:
        config_path.write_text(_DEFAULT_CONFIG_TEMPLATE, encoding="utf-8")
    except Exception:
        pass  # Best-effort: don't crash if CWD is read-only
