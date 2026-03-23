"""
Thermal guidance module — analyzes peak temperatures from benchmark runs.

Compares CPU/GPU peak temps against safe thresholds and returns a finding
dict in the same format as other agent_tools checks. Generates plain-English
guidance when temps indicate throttling risk.
"""

from typing import Optional

# Thresholds per the design doc
CPU_WARN_THRESHOLD = 85.0  # °C — most desktop CPUs throttle around 95-100°C
GPU_WARN_THRESHOLD = 90.0  # °C — most GPUs throttle around 93-100°C


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
