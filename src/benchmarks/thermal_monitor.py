"""
Background thermal monitor — polls LibreHardwareMonitor during benchmarks.

Runs a daemon thread that samples CPU/GPU temperatures at a fixed interval,
tracking peak values. Start before a benchmark, stop after, then read peaks.
"""

import json
import threading
import time
import urllib.request
from typing import Optional

from src.collectors.sub.lhm_sidecar import LHM_URL

_DEFAULT_POLL_INTERVAL = 1.0  # seconds between temp samples


def _parse_temps_from_lhm(data: dict) -> dict[str, float]:
    """
    Recursively walk the LHM JSON tree and extract all temperature sensor values.

    Returns e.g. {"CPU Package": 72.0, "GPU Core": 65.5, "CPU Core #1": 71.0, ...}
    """
    temps: dict[str, float] = {}

    def _walk(node: dict | list, parent_label: str = "") -> None:
        if isinstance(node, list):
            for item in node:
                _walk(item, parent_label)
            return
        if not isinstance(node, dict):
            return

        label = node.get("Text", "")
        children = node.get("Children", [])

        # LHM groups sensors under a "Temperatures" node
        if label == "Temperatures":
            for child in children:
                name = child.get("Text", "Unknown")
                value_str = child.get("Value", "")
                try:
                    # Values look like "72.3 °C" or "- °C" when inactive
                    cleaned = value_str.replace("°C", "").replace(",", ".").strip()
                    if cleaned and cleaned != "-":
                        temps[f"{parent_label}{name}"] = float(cleaned)
                except (ValueError, AttributeError):
                    pass
        else:
            # Recurse into children, passing the hardware component label
            next_label = f"{label} > " if label else parent_label
            for child in children:
                _walk(child, next_label)

    _walk(data)
    return temps


def _fetch_temps() -> dict[str, float]:
    """Poll LHM once and return parsed temps. Returns {} on failure."""
    try:
        req = urllib.request.Request(LHM_URL)
        with urllib.request.urlopen(req, timeout=2) as resp:
            data = json.loads(resp.read())
            return _parse_temps_from_lhm(data)
    except Exception:
        return {}


class ThermalMonitor:
    """
    Background temperature sampler.

    Usage:
        monitor = ThermalMonitor()
        monitor.start()
        # ... run benchmark ...
        monitor.stop()
        peaks = monitor.get_peak_temps()
    """

    def __init__(self, poll_interval: float = _DEFAULT_POLL_INTERVAL):
        self._interval = poll_interval
        self._peak_temps: dict[str, float] = {}
        self._samples: int = 0
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Begin background temperature polling."""
        if self._thread is not None and self._thread.is_alive():
            return  # already running

        self._stop_event.clear()
        self._peak_temps.clear()
        self._samples = 0
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop background polling and wait for the thread to finish."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _poll_loop(self) -> None:
        """Polling loop — runs on daemon thread."""
        while not self._stop_event.is_set():
            temps = _fetch_temps()
            if temps:
                with self._lock:
                    self._samples += 1
                    for sensor, value in temps.items():
                        if sensor not in self._peak_temps or value > self._peak_temps[sensor]:
                            self._peak_temps[sensor] = value
            self._stop_event.wait(self._interval)

    def get_peak_temps(self) -> dict[str, float]:
        """
        Return peak temperatures observed during monitoring.

        Returns e.g.:
        {
            "CPU Package": 85.2,
            "GPU Core": 72.0,
            "CPU Core #1": 84.5,
            ...
        }
        """
        with self._lock:
            return dict(self._peak_temps)

    @property
    def sample_count(self) -> int:
        with self._lock:
            return self._samples

    def get_cpu_peak(self) -> Optional[float]:
        """Return the highest CPU temperature seen, or None if no CPU temps recorded."""
        with self._lock:
            cpu_temps = [
                v for k, v in self._peak_temps.items()
                if "cpu" in k.lower() and "package" in k.lower()
            ]
            if not cpu_temps:
                # Fall back to any CPU core temp
                cpu_temps = [v for k, v in self._peak_temps.items() if "cpu" in k.lower()]
            return max(cpu_temps) if cpu_temps else None

    def get_gpu_peak(self) -> Optional[float]:
        """Return the highest GPU temperature seen, or None if no GPU temps recorded."""
        with self._lock:
            gpu_temps = [v for k, v in self._peak_temps.items() if "gpu" in k.lower()]
            return max(gpu_temps) if gpu_temps else None
