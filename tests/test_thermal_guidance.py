import pytest
from src.agent_tools.thermal_guidance import (
    analyze_thermals,
    check_idle_thermals,
    CPU_WARN_THRESHOLD,
    GPU_WARN_THRESHOLD,
    CPU_IDLE_WARN,
    GPU_IDLE_WARN,
)


# ── No thermal data ──────────────────────────────────────────────────────────

def test_no_data_returns_unknown():
    result = analyze_thermals({})
    assert result["check"] == "thermals"
    assert result["status"] == "UNKNOWN"
    assert "unavailable" in result["message"].lower()
    assert result["can_auto_fix"] is False


# ── Healthy temps ─────────────────────────────────────────────────────────────

def test_healthy_temps():
    temps = {"CPU Package": 65.0, "GPU Core": 70.0}
    result = analyze_thermals(temps, cpu_peak=65.0, gpu_peak=70.0)
    assert result["status"] == "OK"
    assert "healthy" in result["message"].lower()
    assert result["cpu_peak"] == 65.0
    assert result["gpu_peak"] == 70.0


# ── CPU warning (warm, not critical) ─────────────────────────────────────────

def test_cpu_warm():
    temps = {"CPU Package": 87.0, "GPU Core": 70.0}
    result = analyze_thermals(temps, cpu_peak=87.0, gpu_peak=70.0)
    assert result["status"] == "WARNING"
    assert "87°C" in result["message"]
    assert "headroom" in result["message"].lower()


# ── CPU critical (throttling) ────────────────────────────────────────────────

def test_cpu_critical():
    temps = {"CPU Package": 96.0, "GPU Core": 70.0}
    result = analyze_thermals(temps, cpu_peak=96.0, gpu_peak=70.0)
    assert result["status"] == "WARNING"
    assert "96°C" in result["message"]
    assert "throttling" in result["message"].lower()


# ── GPU warning (warm, not critical) ─────────────────────────────────────────

def test_gpu_warm():
    temps = {"CPU Package": 70.0, "GPU Core": 91.0}
    result = analyze_thermals(temps, cpu_peak=70.0, gpu_peak=91.0)
    assert result["status"] == "WARNING"
    assert "91°C" in result["message"]


# ── GPU critical (throttling) ────────────────────────────────────────────────

def test_gpu_critical():
    temps = {"CPU Package": 70.0, "GPU Core": 97.0}
    result = analyze_thermals(temps, cpu_peak=70.0, gpu_peak=97.0)
    assert result["status"] == "WARNING"
    assert "97°C" in result["message"]
    assert "throttling" in result["message"].lower()


# ── Both CPU and GPU warning ─────────────────────────────────────────────────

def test_both_warning():
    temps = {"CPU Package": 88.0, "GPU Core": 92.0}
    result = analyze_thermals(temps, cpu_peak=88.0, gpu_peak=92.0)
    assert result["status"] == "WARNING"
    assert "88°C" in result["message"]
    assert "92°C" in result["message"]


# ── Threshold boundary: exactly at threshold ─────────────────────────────────

def test_cpu_exactly_at_threshold():
    temps = {"CPU Package": CPU_WARN_THRESHOLD}
    result = analyze_thermals(temps, cpu_peak=CPU_WARN_THRESHOLD, gpu_peak=None)
    assert result["status"] == "WARNING"


def test_gpu_exactly_at_threshold():
    temps = {"GPU Core": GPU_WARN_THRESHOLD}
    result = analyze_thermals(temps, cpu_peak=None, gpu_peak=GPU_WARN_THRESHOLD)
    assert result["status"] == "WARNING"


# ── Just below threshold ─────────────────────────────────────────────────────

def test_cpu_just_below_threshold():
    temps = {"CPU Package": CPU_WARN_THRESHOLD - 0.1}
    result = analyze_thermals(temps, cpu_peak=CPU_WARN_THRESHOLD - 0.1, gpu_peak=None)
    assert result["status"] == "OK"


def test_gpu_just_below_threshold():
    temps = {"GPU Core": GPU_WARN_THRESHOLD - 0.1}
    result = analyze_thermals(temps, cpu_peak=None, gpu_peak=GPU_WARN_THRESHOLD - 0.1)
    assert result["status"] == "OK"


# ── Auto-derive peaks from temp dict ─────────────────────────────────────────

def test_derive_peaks_from_dict():
    """When cpu_peak/gpu_peak not provided, derive from the temp dict keys."""
    temps = {"CPU Package": 90.0, "GPU Core": 80.0}
    result = analyze_thermals(temps)  # no explicit peaks
    assert result["status"] == "WARNING"  # CPU 90 > 85 threshold
    assert result["cpu_peak"] == 90.0
    assert result["gpu_peak"] == 80.0


# ── Only CPU sensors ─────────────────────────────────────────────────────────

def test_only_cpu_sensors():
    temps = {"CPU Package": 70.0, "CPU Core #1": 68.0}
    result = analyze_thermals(temps)
    assert result["status"] == "OK"
    assert result["gpu_peak"] is None


# ── Only GPU sensors ─────────────────────────────────────────────────────────

def test_only_gpu_sensors():
    temps = {"GPU Core": 70.0}
    result = analyze_thermals(temps)
    assert result["status"] == "OK"
    assert result["cpu_peak"] is None


# ── Finding dict structure ───────────────────────────────────────────────────

def test_finding_dict_structure():
    """Verify the finding dict has all required keys for pipeline compatibility."""
    result = analyze_thermals({"CPU Package": 70.0}, cpu_peak=70.0, gpu_peak=None)
    assert "check" in result
    assert "status" in result
    assert "message" in result
    assert "can_auto_fix" in result
    assert result["can_auto_fix"] is False  # thermal issues are never auto-fixable


# ── Pre-benchmark idle thermal check ─────────────────────────────────────────

def test_idle_check_no_data():
    """Empty temps dict → safe (no data to judge)."""
    result = check_idle_thermals({})
    assert result["safe"] is True
    assert result["cpu_temp"] is None
    assert result["gpu_temp"] is None


def test_idle_check_cool_system():
    """Temps well below idle thresholds → safe."""
    temps = {"Intel Core i7 > CPU Package": 45.0, "NVIDIA RTX 3080 > GPU Core": 38.0}
    result = check_idle_thermals(temps)
    assert result["safe"] is True
    assert "safe to benchmark" in result["message"].lower()


def test_idle_check_hot_cpu():
    """CPU above idle threshold → not safe."""
    temps = {"Intel Core i7 > CPU Package": 78.0, "NVIDIA RTX 3080 > GPU Core": 40.0}
    result = check_idle_thermals(temps)
    assert result["safe"] is False
    assert result["cpu_temp"] == 78.0
    assert "78°C" in result["message"]
    assert "cool down" in result["message"].lower()


def test_idle_check_hot_gpu():
    """GPU above idle threshold → not safe."""
    temps = {"Intel Core i7 > CPU Package": 45.0, "NVIDIA RTX 3080 > GPU Core": 82.0}
    result = check_idle_thermals(temps)
    assert result["safe"] is False
    assert result["gpu_temp"] == 82.0
    assert "82°C" in result["message"]


def test_idle_check_both_hot():
    """Both CPU and GPU above idle thresholds → not safe, both mentioned."""
    temps = {"Intel Core i7 > CPU Package": 76.0, "NVIDIA RTX 3080 > GPU Core": 81.0}
    result = check_idle_thermals(temps)
    assert result["safe"] is False
    assert "76°C" in result["message"]
    assert "81°C" in result["message"]


def test_idle_check_exactly_at_threshold():
    """Exactly at idle threshold → not safe (≥ comparison)."""
    temps = {"Intel Core i7 > CPU Package": CPU_IDLE_WARN}
    result = check_idle_thermals(temps)
    assert result["safe"] is False


def test_idle_check_just_below_threshold():
    """Just below idle threshold → safe."""
    temps = {"Intel Core i7 > CPU Package": CPU_IDLE_WARN - 0.1}
    result = check_idle_thermals(temps)
    assert result["safe"] is True


def test_idle_check_explicit_overrides():
    """Explicit cpu_temp/gpu_temp override the derived values."""
    temps = {"Intel Core i7 > CPU Package": 45.0}  # cool in the dict
    result = check_idle_thermals(temps, cpu_temp=80.0, gpu_temp=85.0)
    assert result["safe"] is False
    assert result["cpu_temp"] == 80.0
    assert result["gpu_temp"] == 85.0


def test_idle_check_return_structure():
    """Verify all expected keys are present."""
    result = check_idle_thermals({"CPU Package": 50.0})
    assert "safe" in result
    assert "cpu_temp" in result
    assert "gpu_temp" in result
    assert "message" in result
