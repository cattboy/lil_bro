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
    failure_reason: str = "",
) -> dict:
    """
    Analyze peak temperatures from a benchmark run.

    Args:
        peak_temps: Full dict of sensor_name → peak_temp from ThermalMonitor.
        cpu_peak: Pre-computed CPU peak (optional, computed from peak_temps if None).
        gpu_peak: Pre-computed GPU peak (optional, computed from peak_temps if None).
        failure_reason: Optional cause string (from ``describe_sidecar_failure``) to
            append when no thermal data was captured, so the "unavailable" message
            says WHY instead of just that LHM wasn't running.

    Returns:
        Standard finding dict: {check, status, message, can_auto_fix, ...}
    """
    if not peak_temps:
        base = "Thermal data unavailable — LibreHardwareMonitor was not running during benchmark."
        return {
            "check": "thermals",
            "status": "UNKNOWN",
            "message": f"{base} {failure_reason}".strip() if failure_reason else base,
            "can_auto_fix": False,
        }

    # Derive peaks if not provided
    if cpu_peak is None:
        cpu_peak = derive_cpu_temp(peak_temps)

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

# Sensors that should never be used as the representative CPU temperature.
# Core Max and Hotspot read higher than the package die temp and would produce
# false-positive throttling warnings. VRM sensors measure voltage-regulator heat.
_CPU_EXCLUDE_TERMS = ("hotspot", "hot spot", "vrm", "vr ", "core max", "max core")


def derive_cpu_temp(temps: dict[str, float]) -> Optional[float]:
    """Extract the CPU die temperature from a sensor snapshot.

    Priority order:
    1. CPU Package  — the standard die temp for Intel and most AMD CPUs
    2. Tctl / Tdie  — AMD Ryzen primary sensor (LHM label has no "cpu" prefix)
    3. Any CPU sensor excluding hotspot, VRM, and Core Max derivatives
    """
    # P1: CPU Package — explicit package sensor, most reliable
    pkg = [v for k, v in temps.items()
           if "cpu" in k.lower() and "package" in k.lower()]
    if pkg:
        return max(pkg)

    # P2: AMD Tctl/Tdie — LHM sensor name contains no "cpu", e.g.
    #     "AMD Ryzen 9 5900X > Core (Tctl/Tdie)"
    tctl = [v for k, v in temps.items()
            if "tctl" in k.lower() or "tdie" in k.lower()]
    if tctl:
        return max(tctl)

    # P3: Any CPU sensor that is not a hotspot, VRM, or derived-max reading.
    # "gpu" guard is defensive — prevents matching a sensor whose hardware node
    # path happens to contain "cpu" (e.g. "CPU VRM" on a GPU sub-board).
    safe = [v for k, v in temps.items()
            if "cpu" in k.lower()
            and "gpu" not in k.lower()
            and not any(excl in k.lower() for excl in _CPU_EXCLUDE_TERMS)]
    return max(safe) if safe else None


def derive_gpu_temp(temps: dict[str, float]) -> Optional[float]:
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
        cpu_temp = derive_cpu_temp(temps)
    if gpu_temp is None:
        gpu_temp = derive_gpu_temp(temps)

    warnings = []

    if cpu_temp is not None and cpu_temp >= CPU_IDLE_WARN:
        if cpu_temp >= 80.0:
            warnings.append(
                f"HAALLLPP CPU is at {cpu_temp:.0f}°C AT IDLE — clean yo fans or repaste "
                f"the PC, lil_bro's home is on FIRE. Under work-loads this thing will hit "
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


# ── Sidecar launch-failure attribution ───────────────────────────────────────
# When the LHM sidecar fails to provide thermal data, three consumers need a
# plain-English cause: the Dashboard thermal card, the benchmark thermal gate
# (which skips Cinebench when temps are unavailable), and the CLI startup scan.
# LHMSidecar records WHICH way it failed (``last_failure_kind``); this module
# turns that kind + cheap environmental probes into a user-facing cause + action.
#
# Failure kinds set by LHMSidecar.start() per branch -- except ``no_sensors``,
# which the launch site determines when start() SUCCEEDS but no CPU sensor ever
# appears (the PawnIO / Secure-Boot case: start() returns True with empty data):
#   port_in_use, not_found, elevation_failed, launch_error,
#   exited_immediately, timeout, no_sensors, unknown
#
# classify_sidecar_failure is PURE (kind + probes in, message out) so it is
# trivially unit-testable. describe_sidecar_failure does the I/O (gathers probes)
# and NEVER raises -- it runs inside an already-failing path.

_LHM_PORT_DEFAULT = 8085


def classify_sidecar_failure(
    kind: str,
    probes: Optional[dict] = None,
    returncode: Optional[int] = None,
    stderr_lines: Optional[list[str]] = None,
) -> dict:
    """Map a sidecar failure ``kind`` + environmental ``probes`` to a cause+action.

    Pure: no I/O, no side effects. ``probes`` keys (all optional):
        ``pawnio_installed`` (bool), ``port_owner`` (str|None),
        ``exe_present`` (bool|None), ``is_admin`` (bool).
    ``returncode``/``stderr_lines`` are only consulted for the ``exited_immediately``
    branch (the one kind that actually carries them). Returns
    ``{"status": "WARNING", "message": str}``.
    """
    probes = probes or {}
    port_owner = probes.get("port_owner")
    pawnio = probes.get("pawnio_installed", False)

    if kind == "port_in_use":
        who = f" by {port_owner}" if port_owner else " by another application"
        msg = (
            f"Port {_LHM_PORT_DEFAULT} is in use{who}. "
            "Close it and retry to restore thermal monitoring."
        )
    elif kind == "not_found":
        msg = (
            "The thermal helper (lhm-server.exe) is missing from the install -- "
            "antivirus may have quarantined it. Reinstall lil_bro, then retry."
        )
    elif kind == "elevation_failed":
        msg = (
            "Elevation for the thermal helper was declined. Thermal monitoring "
            "needs admin rights -- retry and accept the prompt."
        )
    elif kind == "launch_error":
        msg = (
            "The thermal helper could not launch -- often antivirus blocking it. "
            "Add an exclusion for lhm-server.exe, then retry."
        )
    elif kind == "exited_immediately":
        if _is_dotnet_host_error(returncode, stderr_lines):
            msg = (
                "The thermal helper failed to start its bundled runtime. "
                "Please report this; reinstalling lil_bro may help."
            )
        else:
            msg = (
                "The thermal helper exited immediately -- often antivirus quarantine. "
                "Add an exclusion for lhm-server.exe, then retry."
            )
    elif kind == "timeout":
        if not pawnio:
            msg = (
                "The thermal helper started but no sensors responded, and the PawnIO "
                "driver isn't installed. Retry to reinstall it."
            )
        else:
            msg = "The thermal helper started but didn't respond in time. Retry."
    elif kind == "no_sensors":
        if not pawnio:
            msg = (
                "Thermal helper is running but the PawnIO sensor driver was blocked "
                "(often Secure Boot / driver signing). Retry to reinstall it."
            )
        else:
            msg = (
                "Thermal helper is running but reported no CPU sensors. "
                "Retry, or verify PawnIO loaded."
            )
    else:  # unknown / catch-all -- never leave the user without an action
        msg = (
            "Thermal monitoring is unavailable. Retry, or check antivirus "
            f"and that port {_LHM_PORT_DEFAULT} is free."
        )

    return {"status": "WARNING", "message": msg}


def _is_dotnet_host_error(
    returncode: Optional[int], stderr_lines: Optional[list[str]]
) -> bool:
    """True if the failure looks like a missing/broken .NET host.

    Defensive only: the sidecar ships self-contained (bundles .NET 8), so this
    should never fire in the field -- if it does, it points at a build regression,
    not a user-fixable prerequisite. 0x80008096 is hostfxr's "must install .NET".
    """
    if returncode is not None and returncode in (0x80008096, -2147450730):
        return True
    text = " ".join(stderr_lines or []).lower()
    return "hostfxr" in text or "you must install" in text


def _gather_sidecar_probes() -> dict:
    """Collect cheap, read-only environmental facts for failure attribution.

    Each probe is independently guarded -- this runs inside an already-failing
    path and must never raise. ``psutil.net_connections`` (inside ``_port_owner``)
    can raise AccessDenied on a non-elevated run, hence the per-probe try/except.
    """
    probes: dict = {"pawnio_installed": False, "port_owner": None, "is_admin": False}
    try:
        from src.utils.pawnio_check import is_pawnio_installed
        probes["pawnio_installed"] = is_pawnio_installed()
    except Exception:
        pass  # safe: probe is best-effort
    try:
        from src.collectors.sub.lhm_process_utils import _port_owner
        from src.collectors.sub.lhm_http import LHM_PORT
        probes["port_owner"] = _port_owner(LHM_PORT)
    except Exception:
        pass  # safe: probe is best-effort
    try:
        from src.utils.platform import is_admin
        probes["is_admin"] = is_admin()
    except Exception:
        pass  # safe: probe is best-effort
    return probes


def describe_sidecar_failure(lhm, no_sensors: bool = False) -> str:
    """Return a user-facing cause+action for a failed/sensorless thermal sidecar.

    ``lhm`` is an LHMSidecar instance (reads ``last_failure_kind`` /
    ``last_returncode`` / ``last_stderr_lines``). Pass ``no_sensors=True`` when
    start() SUCCEEDED but no CPU sensor appeared after the retry window. Never
    raises -- it is called on an already-failing path.
    """
    try:
        kind = "no_sensors" if no_sensors else (getattr(lhm, "last_failure_kind", None) or "unknown")
        return classify_sidecar_failure(
            kind,
            _gather_sidecar_probes(),
            returncode=getattr(lhm, "last_returncode", None),
            stderr_lines=getattr(lhm, "last_stderr_lines", None),
        )["message"]
    except Exception:
        return (
            "Thermal monitoring is unavailable. Retry, or check antivirus "
            f"and that port {_LHM_PORT_DEFAULT} is free."
        )
