"""
Background thermal monitor — polls LibreHardwareMonitor during benchmarks.

Runs a daemon thread that samples CPU/GPU temperatures at a fixed interval,
tracking peak values. Start before a benchmark, stop after, then read peaks.

Also provides a single-shot ``fetch_snapshot()`` for pre-benchmark idle checks.
"""

import json
import threading
import time
import urllib.request
from typing import Optional

from src.collectors.sub.lhm_sidecar import LHM_URL
from src.agent_tools.thermal_guidance import derive_cpu_temp
from src.config import config as _cfg

_DEFAULT_POLL_INTERVAL = _cfg.thermal.poll_interval  # seconds between temp samples


def _extract_sensor_temp(child: dict) -> Optional[float]:
    """
    Extract a temperature value from an LHM sensor node.

    Prefers the numeric ``RawValue`` field (added by LHM's HttpServer for
    external consumers) over string-parsing the formatted ``Value`` field.
    Returns None if the sensor is inactive or unparseable.
    """
    # Prefer RawValue — a plain float, no locale issues
    raw = child.get("RawValue")
    if raw is not None:
        try:
            val = float(raw)
            # LHM uses 0.0 or very small negatives for inactive sensors
            if val > 0.0:
                return val
        except (ValueError, TypeError):
            pass

    # Fallback: parse the formatted Value string ("72.3 °C", "- °C", "72,5 °C")
    value_str = child.get("Value", "")
    try:
        cleaned = value_str.replace("°C", "").replace(",", ".").strip()
        if cleaned and cleaned != "-":
            return float(cleaned)
    except (ValueError, AttributeError):
        pass

    return None


def _parse_temps_from_lhm(data: dict) -> dict[str, float]:
    """
    Recursively walk the LHM JSON tree and extract all temperature sensor values.

    Returns e.g. ``{"Intel Core i7 > CPU Package": 72.0, ...}``
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

        # LHM groups sensors under a "Temperatures" type node
        if label == "Temperatures":
            for child in children:
                name = child.get("Text", "Unknown")
                temp = _extract_sensor_temp(child)
                if temp is not None:
                    temps[f"{parent_label}{name}"] = temp
        else:
            # Recurse into children, carrying the hardware component label
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


def fetch_snapshot() -> dict[str, float]:
    """
    Take a single thermal reading from LHM.

    Public entry point for one-shot checks (e.g. pre-benchmark idle temp
    verification).  Returns ``{}`` if LHM is unreachable.
    """
    return _fetch_temps()


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
        """Return the peak CPU die temperature seen, or None if no CPU temps recorded."""
        with self._lock:
            peak_copy = dict(self._peak_temps)
        return derive_cpu_temp(peak_copy)

    def get_gpu_peak(self) -> Optional[float]:
        """Return the highest GPU temperature seen, or None if no GPU temps recorded."""
        with self._lock:
            gpu_temps = [v for k, v in self._peak_temps.items() if "gpu" in k.lower()]
            return max(gpu_temps) if gpu_temps else None


# ── Thermal watchdog ─────────────────────────────────────────────────────────

_WATCHDOG_THRESHOLD = _cfg.thermal.watchdog_threshold  # °C — abort limit for CPU and GPU
_WATCHDOG_SUSTAINED_SECS = 5                           # consecutive seconds over limit before abort
_WATCHDOG_POLL_INTERVAL = _cfg.thermal.poll_interval   # seconds between polls


class ThermalWatchdog:
    """
    Background thermal watchdog — aborts a benchmark if CPU or GPU temperature
    stays critically high for a sustained period.

    Follows the same daemon-thread + threading.Event stop pattern as ThermalMonitor.

    Usage::

        abort_event = threading.Event()
        watchdog = ThermalWatchdog(abort_event)
        watchdog.start()
        # ... benchmark runs ...
        watchdog.stop()
        if watchdog.abort_reason:
            print(watchdog.abort_reason)
    """

    def __init__(
        self,
        abort_event: threading.Event,
        threshold: float = _WATCHDOG_THRESHOLD,
        sustained_secs: int = _WATCHDOG_SUSTAINED_SECS,
        poll_interval: float = _WATCHDOG_POLL_INTERVAL,
    ):
        self._abort_event = abort_event
        self._threshold = threshold
        self._sustained_secs = sustained_secs
        self._interval = poll_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.abort_reason: Optional[str] = None  # written before abort_event fires

    def start(self) -> None:
        """Begin background temperature watchdog."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.abort_reason = None
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop the watchdog thread."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _poll_loop(self) -> None:
        """Polling loop — tracks consecutive seconds over threshold per component."""
        cpu_streak = 0
        gpu_streak = 0

        while not self._stop_event.is_set():
            temps = _fetch_temps()
            if temps:
                cpu_temp = derive_cpu_temp(temps)
                gpu_vals = [v for k, v in temps.items() if "gpu" in k.lower()]
                gpu_temp = max(gpu_vals) if gpu_vals else None

                cpu_streak = cpu_streak + 1 if (cpu_temp and cpu_temp >= self._threshold) else 0
                gpu_streak = gpu_streak + 1 if (gpu_temp and gpu_temp >= self._threshold) else 0

                if cpu_streak >= self._sustained_secs:
                    self.abort_reason = (
                        f"CPU held at {cpu_temp:.0f}\u00b0C for {self._sustained_secs}+ seconds"
                        " \u2014 benchmark aborted to prevent thermal damage."
                    )
                    self._abort_event.set()
                    return

                if gpu_streak >= self._sustained_secs:
                    self.abort_reason = (
                        f"GPU held at {gpu_temp:.0f}\u00b0C for {self._sustained_secs}+ seconds"
                        " \u2014 benchmark aborted to prevent thermal damage."
                    )
                    self._abort_event.set()
                    return

            self._stop_event.wait(self._interval)
