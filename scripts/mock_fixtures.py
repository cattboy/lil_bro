"""Fixture data for the developer mock GUI (scripts/mock_gui.py).

Pure data + tiny helpers — no Qt imports. NVIDIA fixtures are built from the
production constants in ``src/utils/nvidia_npi.py`` (``SETTING_IDS`` /
``TARGET_VALUES`` / ``calculate_fps_cap``) and ``get_preset`` so they can
never drift from the real analyzer's targets.

Call ``nvidia_specs()`` AFTER ``Dashboard.seed_dlss_priority`` has run:
``get_preset`` resolves the DLSS letter from the live config priority, and the
"ok" fixture's raw settings must match whatever the analyzer will expect.
"""

from __future__ import annotations

import copy
import math

from src.utils.dlss_presets import get_preset
from src.utils.nvidia_npi import SETTING_IDS, TARGET_VALUES, calculate_fps_cap

# ── Stat-card snapshots (SystemStatsWorker._tick shape, minus the raw ──────
# _cpu_c/_gpu_c floats — the thermal chart is driven separately by
# thermal_series()/the animation timer so the Stats combo never knocks an
# "offline" chart back online, and minus mouse_hz so the Mouse combo stays
# the sole owner of the mouse card's state).
SNAPSHOTS: dict[str, dict] = {
    "normal": {
        "cpu_usage": "23%", "cpu_temp": "54°C",
        "gpu_temp": "61°C", "ram_used": "17.8 GB",
    },
    "hot": {
        "cpu_usage": "98%", "cpu_temp": "96°C",
        "gpu_temp": "89°C", "ram_used": "31.2 GB",
    },
    "missing": {},  # Dashboard.apply_snapshot({}) renders all four cards as "—"
}

# Base (cpu_c, gpu_c) the 1 Hz animation timer oscillates around, per stats key.
ANIM_BASES: dict[str, tuple[float, float]] = {
    "normal": (54.0, 61.0),
    "hot": (92.0, 86.0),
    "missing": (54.0, 61.0),
}


def thermal_series(kind: str) -> list[tuple[float, float]]:
    """120 (cpu_c, gpu_c) samples — fills the chart's full 2-minute window.

    "normal" stays below the 75° warning line; "warning" ramps across it;
    "critical" ramps across both 75° and 85° (legend digits turn coral).
    """
    n = 120
    out: list[tuple[float, float]] = []
    for i in range(n):
        t = i / (n - 1)
        if kind == "warning":
            cpu = 60.0 + 20.0 * t + 1.5 * math.sin(i / 4.0)
            gpu = 56.0 + 21.0 * t + 1.2 * math.sin(i / 5.0 + 1.0)
        elif kind == "critical":
            cpu = 65.0 + 27.0 * t + 1.5 * math.sin(i / 4.0)
            gpu = 60.0 + 29.0 * t + 1.2 * math.sin(i / 5.0 + 1.0)
        else:  # "normal"
            cpu = 55.0 + 8.0 * math.sin(i / 12.0)
            gpu = 62.0 + 6.0 * math.sin(i / 9.0 + 1.5)
        out.append((round(cpu, 1), round(gpu, 1)))
    return out


# ── Mouse poll results (fed to the real Dashboard.receive_poll_result) ─────
MOUSE_RESULTS: dict[str, dict] = {
    "ok_1000":  {"current_hz": 1000, "status": "OK"},       # mint "Excellent…"
    "warn_500": {"current_hz": 500,  "status": "WARNING"},  # amber "Acceptable…"
    "low_125":  {"current_hz": 125,  "status": "WARNING"},  # coral + proposal text/tooltip
    "error":    {"current_hz": 0,    "status": "ERROR"},    # coral "Measurement failed"
    # "not_measured" -> reset_mouse_card(); "measuring" -> real button click
    # with the fake worker patched in (see mock_gui.py).
}


def reset_mouse_card(card) -> None:
    """Restore MousePollCard's "Not measured" constructor state.

    The card has no public reset — once ``apply_pipeline_result`` runs,
    ``_mouse_manually_measured`` latches and snapshots are ignored. This is
    the mock's one documented private-attr touch (mirrors mouse_poll_card.py
    __init__ exactly).
    """
    card._mouse_manually_measured = False
    card._poll_val.setText("—")
    card._poll_status.setText("Not measured")
    card._poll_status.setToolTip("")
    card._set_poll_sev("")
    card._poll_btn.setEnabled(True)


# ── DisplayCapabilities fixtures ────────────────────────────────────────────
DISPLAYS: dict[str, list[dict]] = {
    "optimal": [
        {"device": r"\\.\DISPLAY1", "current_refresh_hz": 144, "max_refresh_hz": 144,
         "at_resolution": "2560x1440", "source": "edid", "edid_declared_max_hz": 144},
    ],
    "suboptimal": [
        {"device": r"\\.\DISPLAY1", "current_refresh_hz": 60, "max_refresh_hz": 144,
         "at_resolution": "1920x1080", "source": "edid", "edid_declared_max_hz": 144},
    ],
    "wmi": [
        {"device": "WMI:LEN T2454pA", "current_refresh_hz": 60, "max_refresh_hz": 0,
         "at_resolution": "", "source": "wmi", "edid_declared_max_hz": None},
    ],
    "empty": [],
    "multi": [
        {"device": r"\\.\DISPLAY1", "current_refresh_hz": 144, "max_refresh_hz": 144,
         "at_resolution": "2560x1440", "source": "edid", "edid_declared_max_hz": 144},
        {"device": r"\\.\DISPLAY2", "current_refresh_hz": 60, "max_refresh_hz": 165,
         "at_resolution": "2560x1440", "source": "edid", "edid_declared_max_hz": 165},
        {"device": r"\\.\DISPLAY3", "current_refresh_hz": 240, "max_refresh_hz": 240,
         "at_resolution": "1920x1080", "source": "edid", "edid_declared_max_hz": 240},
    ],
}


def displays(key: str) -> list[dict]:
    """Deep copy so the mock fix handler can mutate without corrupting fixtures."""
    return copy.deepcopy(DISPLAYS[key])


# ── NVIDIA specs (consumed by set_nvidia_data + the REAL analyze_nvidia_profile)


def _target_raw() -> dict[int, int]:
    return {SETTING_IDS[k]: v for k, v in TARGET_VALUES.items()}


def nvidia_specs(state: str) -> dict:
    """Full specs dict for one NVIDIA scenario.

    states: "ok" (green per-setting checklist), "warning" (red→green deltas on
    every setting), "gtx_no_dlss" (profile card only, DLSS card hidden),
    "no_gpu" (both cards hidden).
    """
    if state == "no_gpu":
        return {"NVIDIA": []}

    cap = calculate_fps_cap(144)  # 139 — matches the 144 Hz fixture display

    if state == "gtx_no_dlss":
        raw = _target_raw()
        raw[SETTING_IDS["fps_limiter_v3"]] = cap
        return {
            "NVIDIA": [{"GPU": "NVIDIA GeForce GTX 1080", "ReBAR": False}],
            "DisplayCapabilities": displays("optimal"),
            "NVIDIAProfile": {
                "available": True,
                "raw_settings": raw,
                "gsync_enabled": True, "vsync_mode": "force_on", "fps_cap": cap,
                "rebar_driver": False, "dlss_preset": None,
                "power_mgmt": "max_performance",
            },
        }

    gpu_name = "NVIDIA GeForce RTX 4080"
    preset = get_preset(gpu_name)  # priority from live config — seed first
    raw = _target_raw()
    raw[SETTING_IDS["fps_limiter_v3"]] = cap
    raw[SETTING_IDS["dlss_preset_letter"]] = preset.value if preset else 13

    specs = {
        "NVIDIA": [{"GPU": gpu_name, "ReBAR": True}],
        "DisplayCapabilities": displays("optimal"),
        "NVIDIAProfile": {
            "available": True,
            "raw_settings": raw,
            "gsync_enabled": True, "vsync_mode": "force_on", "fps_cap": cap,
            "rebar_driver": True,
            "dlss_preset": preset.letter if preset else "M",
            "power_mgmt": "max_performance",
        },
    }

    if state == "warning":
        raw[SETTING_IDS["gsync_global_feature"]] = 0
        raw[SETTING_IDS["vsync"]] = 0
        del raw[SETTING_IDS["fps_limiter_v3"]]
        raw[SETTING_IDS["rebar_enable"]] = 0
        raw[SETTING_IDS["dlss_preset_letter"]] = 1  # Preset A
        raw[SETTING_IDS["power_mgmt"]] = 0          # Adaptive
        specs["NVIDIAProfile"].update({
            "gsync_enabled": False, "vsync_mode": "off", "fps_cap": None,
            "rebar_driver": False, "dlss_preset": "A", "power_mgmt": "adaptive",
        })

    return specs


# ── Whole-dashboard scenario presets ────────────────────────────────────────
SCENARIOS: dict[str, dict] = {
    "All optimal": {
        "stats": "normal", "thermal": "normal", "mouse": "ok_1000",
        "monitors": "optimal", "nvidia": "ok", "animate": True,
    },
    "Mixed issues": {
        "stats": "normal", "thermal": "warning", "mouse": "warn_500",
        "monitors": "suboptimal", "nvidia": "warning", "animate": False,
    },
    "Everything broken": {
        "stats": "hot", "thermal": "critical", "mouse": "low_125",
        "monitors": "wmi", "nvidia": "warning", "animate": False,
    },
    "Fresh install": {
        "stats": "missing", "thermal": "offline", "mouse": "not_measured",
        "monitors": "empty", "nvidia": "no_gpu", "animate": False,
    },
}
