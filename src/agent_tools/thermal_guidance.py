"""
Thermal guidance module — analyzes peak temperatures from benchmark runs.

Compares CPU/GPU peak temps against safe thresholds and returns a finding
dict in the same format as other agent_tools checks. Generates plain-English
guidance when temps indicate throttling risk.

Also provides ``check_idle_thermals()`` for pre-benchmark safety gating.
"""

from typing import Optional

# ── Post-benchmark thresholds (peak temps under full load) ───────────────────
CPU_WARN_THRESHOLD = 85.0  # °C — most desktop CPUs throttle around 95-100°C
GPU_WARN_THRESHOLD = 90.0  # °C — most GPUs throttle around 93-100°C

# ── Pre-benchmark idle thresholds ────────────────────────────────────────────
# If the system is already this hot at idle/light load, running a full
# benchmark will almost certainly push it into throttling or shutdown territory.
CPU_IDLE_WARN = 75.0  # °C — idle CPU this hot → under load it'll hit 90°C+
GPU_IDLE_WARN = 80.0  # °C — idle GPU this hot → under load it'll hit 95°C+


def analyze_thermals(
    peak_temps: dict[str, float],
    cpu_peak: Optional[float] = None,
    gpu_peak: Optional[float] = None,
) -> dict:
    """
    Analyze peak temperatures from a benchmark run.

    Args:
        peak_temps: Full dict of sensor_name → peak_temp from ThermalMonitor.
        cpu_peak: Pre-computed CPU peak (optional, computed from peak_temps if None).
        gpu_peak: Pre-computed GPU peak (optional, computed from peak_temps if None).

    Returns:
        Standard finding dict: {check, status, message, can_auto_fix, ...}
    """
    if not peak_temps:
        return {
            "check": "thermals",
            "status": "UNKNOWN",
            "message": "Thermal data unavailable — LibreHardwareMonitor was not running during benchmark.",
            "can_auto_fix": False,
        }

    # Derive peaks if not provided
    if cpu_peak is None:
        cpu_temps = [v for k, v in peak_temps.items() if "cpu" in k.lower()]
        cpu_peak = max(cpu_temps) if cpu_temps else None

    if gpu_peak is None:
        gpu_temps = [v for k, v in peak_temps.items() if "gpu" in k.lower()]
        gpu_peak = max(gpu_temps) if gpu_temps else None

    issues = []

    if cpu_peak is not None and cpu_peak >= CPU_WARN_THRESHOLD:
        issues.append(_cpu_guidance(cpu_peak))

    if gpu_peak is not None and gpu_peak >= GPU_WARN_THRESHOLD:
        issues.append(_gpu_guidance(gpu_peak))

    # Build summary
    temp_summary = _format_temp_summary(cpu_peak, gpu_peak)

    if issues:
        combined_guidance = " ".join(issues)
        return {
            "check": "thermals",
            "status": "WARNING",
            "message": f"{temp_summary} {combined_guidance}",
            "can_auto_fix": False,
            "cpu_peak": cpu_peak,
            "gpu_peak": gpu_peak,
            "peak_temps": peak_temps,
        }

    return {
        "check": "thermals",
        "status": "OK",
        "message": f"{temp_summary} Temps look healthy — no throttling risk detected.",
        "can_auto_fix": False,
        "cpu_peak": cpu_peak,
        "gpu_peak": gpu_peak,
        "peak_temps": peak_temps,
    }


def _format_temp_summary(cpu_peak: Optional[float], gpu_peak: Optional[float]) -> str:
    parts = []
    if cpu_peak is not None:
        parts.append(f"CPU peak: {cpu_peak:.1f}°C")
    if gpu_peak is not None:
        parts.append(f"GPU peak: {gpu_peak:.1f}°C")
    if not parts:
        return "No temperature sensors detected."
    return f"[{', '.join(parts)}]"


def _cpu_guidance(peak: float) -> str:
    if peak >= 95.0:
        return (
            f"CPU hit {peak:.0f}°C under load — that's thermal throttling territory. "
            "Your CPU is almost certainly slowing itself down to avoid damage. "
            "Check that your cooler is mounted properly, thermal paste isn't dried out, "
            "and case airflow isn't blocked. If you're on the stock cooler, "
            "a tower cooler or AIO upgrade would make a real difference."
        )
    return (
        f"CPU reached {peak:.0f}°C under load — getting warm. "
        "Not throttling yet, but you don't have much headroom. "
        "Make sure your case fans are running and dust isn't choking the heatsink. "
        "Consider reapplying thermal paste if it's been a couple years."
    )


def _gpu_guidance(peak: float) -> str:
    if peak >= 95.0:
        return (
            f"GPU hit {peak:.0f}°C under load — it's almost certainly throttling. "
            "Check that the GPU fans are spinning, the card isn't sagging, "
            "and the case has enough airflow. If the card runs hot by design, "
            "a more aggressive fan curve in MSI Afterburner or the NVIDIA App can help."
        )
    return (
        f"GPU reached {peak:.0f}°C under load — on the warm side. "
        "It's managing for now, but a custom fan curve could buy you headroom. "
        "Make sure nothing is blocking the GPU's intake fans."
    )


# ── Pre-benchmark idle thermal check ─────────────────────────────────────────

def _derive_cpu_temp(temps: dict[str, float]) -> Optional[float]:
    """Pick the most representative CPU temperature from a snapshot."""
    # Prefer "Package" sensor — it's the overall die temp
    pkg = [v for k, v in temps.items() if "cpu" in k.lower() and "package" in k.lower()]
    if pkg:
        return max(pkg)
    # Fallback to any CPU-labelled sensor
    cpu = [v for k, v in temps.items() if "cpu" in k.lower()]
    return max(cpu) if cpu else None


def _derive_gpu_temp(temps: dict[str, float]) -> Optional[float]:
    """Pick the most representative GPU temperature from a snapshot."""
    gpu = [v for k, v in temps.items() if "gpu" in k.lower()]
    return max(gpu) if gpu else None


def check_idle_thermals(
    temps: dict[str, float],
    cpu_temp: Optional[float] = None,
    gpu_temp: Optional[float] = None,
) -> dict:
    """
    Pre-benchmark safety gate — checks idle/current temps before stressing the system.

    If the system is already running hot at idle, a benchmark could push it into
    thermal throttling or emergency shutdown territory. This check gives the user
    a chance to let the system cool down or fix airflow before proceeding.

    Args:
        temps: Current temperature snapshot from ``fetch_snapshot()``.
        cpu_temp: Explicit CPU temp override (derived from temps if None).
        gpu_temp: Explicit GPU temp override (derived from temps if None).

    Returns:
        dict with keys:
            safe (bool): True if OK to proceed with benchmark.
            cpu_temp (float|None): Current CPU temperature.
            gpu_temp (float|None): Current GPU temperature.
            message (str): Human-readable summary.
    """
    if not temps:
        return {
            "safe": True,
            "cpu_temp": None,
            "gpu_temp": None,
            "message": "No thermal data available — proceeding without pre-check.",
        }

    if cpu_temp is None:
        cpu_temp = _derive_cpu_temp(temps)
    if gpu_temp is None:
        gpu_temp = _derive_gpu_temp(temps)

    warnings = []

    if cpu_temp is not None and cpu_temp >= CPU_IDLE_WARN:
        if cpu_temp >= 80.0:
            warnings.append(
                f"CPU is at {cpu_temp:.0f}°C AT IDLE — clean yo fans or repaste "
                f"your CPU, your PC is dying yo. Under load this thing will hit "
                f"{cpu_temp + 15:.0f}°C+ and throttle hard."
            )
        else:
            warnings.append(
                f"CPU is already at {cpu_temp:.0f}°C at idle — "
                f"under full load it could exceed {cpu_temp + 15:.0f}°C."
            )

    if gpu_temp is not None and gpu_temp >= GPU_IDLE_WARN:
        if gpu_temp >= 80.0:
            warnings.append(
                f"GPU is at {gpu_temp:.0f}°C AT IDLE — that's cooked. "
                f"Check your GPU fans are actually spinning, clean the dust out, "
                f"and make sure your case isn't suffocating it. Under load "
                f"you're looking at {gpu_temp + 15:.0f}°C+ easy."
            )
        else:
            warnings.append(
                f"GPU is already at {gpu_temp:.0f}°C at idle — "
                f"under full load it could exceed {gpu_temp + 15:.0f}°C."
            )

    if warnings:
        guidance = " ".join(warnings) + (
            " Let the system cool down, check case fans and airflow, "
            "or clean dust filters before benchmarking."
        )
        return {
            "safe": False,
            "cpu_temp": cpu_temp,
            "gpu_temp": gpu_temp,
            "message": guidance,
        }

    # Build an "all clear" summary
    parts = []
    if cpu_temp is not None:
        parts.append(f"CPU: {cpu_temp:.0f}°C")
    if gpu_temp is not None:
        parts.append(f"GPU: {gpu_temp:.0f}°C")
    summary = f"Idle temps look good ({', '.join(parts)})" if parts else "Temps normal"

    return {
        "safe": True,
        "cpu_temp": cpu_temp,
        "gpu_temp": gpu_temp,
        "message": f"{summary} — safe to benchmark.",
    }
