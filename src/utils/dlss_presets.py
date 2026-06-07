"""
DLSS preset policy: capability tier + quality/FPS priority resolution.

Owns GPU -> capability classification and the (tier, priority) -> preset-letter
policy. The policy lives here as hardcoded constants (baked into the exe); the
letter <-> NPI-value mechanics stay in ``nvidia_npi.py`` (``DLSS_VALUE_BY_LETTER``).

Data flow::

    specs["NVIDIA"][0]["GPU"]   (e.g. "NVIDIA GeForce RTX 5090")
            |
            v
       classify(name) --> "unsupported"/"unknown" --> get_preset() = None
            |                                              |
       "fp8"/"no_fp8"                          analyzer: skipped msg
            |                                  dashboard: card hidden
            v
    config.nvidia.dlss.priority   (live singleton; seeded QSettings > JSON > "quality")
            |  "quality" | "fps"   (invalid -> "quality" fallback)
            v
       get_preset(name) --> DlssPreset(letter, value, model_name, tier, priority)
            |                          value via DLSS_VALUE_BY_LETTER (nvidia_npi.py)
            +--> _check_dlss .............. raw[dlss_preset_letter] == preset.value
            +--> fix_nvidia_profile (full)  write dlss_preset_letter = preset.value
            +--> fix_nvidia_dlss_preset ... write the two DLSS SettingIDs
            +--> dashboard.set_nvidia_data  "Recommended: DLSS Preset {preset.letter}"

Resolution model (NPI forces ONE global preset letter; the per-mode matrix
collapses to a single default driven by FP8 capability + a quality/FPS lean):

    | tier               | quality | fps |
    | FP8 (RTX 40/50)    |   M     |  L  |
    | no-FP8 (RTX 20/30) |   K     |  K  |
    | unsupported/unknown|  none (DLSS not supported)  |

``quality`` is the quality-leaning choice *between M and L* (M is gen-2
Performance-tuned), NOT NVIDIA's absolute DLAA/Quality default (that is K).
lil_bro's stance: on FP8 hardware, prefer the gen-2 transformer.

E2 ``monitor_aware_priority`` picks a smart default priority from the primary
display before the user toggles: 60 Hz cap -> quality; 4K -> quality; else None.

Import guard: this module imports ``config`` (lazily); ``config.py`` must NEVER
import this module, and ``config.nvidia.dlss.priority`` stays a plain ``str``.
"""

from __future__ import annotations

import re
from typing import Any, NamedTuple

from .nvidia_npi import DLSS_VALUE_BY_LETTER


class DlssPreset(NamedTuple):
    """A resolved DLSS preset to force via NPI."""

    letter: str       # "K" | "L" | "M"
    value: int        # NPI forced-preset value (11/12/13), from DLSS_VALUE_BY_LETTER
    model_name: str   # human-readable model description
    tier: str         # "fp8" | "no_fp8"
    priority: str     # "quality" | "fps"


# Factual model labels, matching docs/dlss_4_5_presets_by_gpu.json.
_MODEL_NAMES: dict[str, str] = {
    "K": "DLSS 4 (Transformer gen-1; NVIDIA DLAA/Quality default, most RT-denoiser-robust)",
    "L": "DLSS 4.5 (Transformer gen-2; tuned for Ultra-Performance mode)",
    "M": "DLSS 4.5 (Transformer gen-2; tuned for Performance mode)",
}

# THE policy table. Update this (and bump the comment) when NVIDIA ships a new model.
_TIERS: dict[str, dict[str, str]] = {
    "fp8":    {"quality": "M", "fps": "L"},   # RTX 40/50: FP8-accelerated gen-2 transformer
    "no_fp8": {"quality": "K", "fps": "K"},   # RTX 20/30: gen-1 (M/L too costly without FP8)
}

_GEN_TIER: dict[str, str] = {"50": "fp8", "40": "fp8", "30": "no_fp8", "20": "no_fp8"}

_DEFAULT_PRIORITY = "quality"
_VALID_PRIORITIES = ("quality", "fps")

# Non-consumer / no-DLSS markers the loose RTX regex would otherwise misread.
_UNSUPPORTED_MARKERS = ("RTX A", "ADA GENERATION", "QUADRO", "TITAN", "GTX")


def _get_gpu_generation(gpu_name: str) -> str | None:
    """Extract RTX generation from a GPU name ('...RTX 4090' -> '40'). None if not RTX."""
    m = re.search(r"RTX\s*(\d)0", gpu_name or "", re.IGNORECASE)
    return m.group(1) + "0" if m else None


def classify(gpu_name: str) -> str:
    """Classify a GPU into a DLSS capability tier.

    Returns one of ``"fp8" | "no_fp8" | "unsupported" | "unknown"``.

    Ordering is load-bearing: the workstation/GTX gate runs BEFORE the generation
    regex so ``"RTX 2000 Ada Generation"`` is rejected rather than misread as gen
    ``"20"``.
    """
    name = (gpu_name or "").upper()
    if not name:
        return "unknown"
    if any(marker in name for marker in _UNSUPPORTED_MARKERS):
        return "unsupported"
    gen = _get_gpu_generation(name)
    if gen is None:
        return "unknown"
    tier = _GEN_TIER.get(gen)
    return tier if tier is not None else "unknown"  # unmapped gen (e.g. future 60-series)


def _resolve_priority() -> str:
    """Read the configured priority from the live ``config`` singleton (validated)."""
    try:
        from src.config import config
        pri = config.nvidia.dlss.priority
    except Exception:
        return _DEFAULT_PRIORITY
    return pri if pri in _VALID_PRIORITIES else _DEFAULT_PRIORITY


def get_preset(gpu_name: str, priority: str | None = None) -> DlssPreset | None:
    """Resolve the DLSS preset to force for ``gpu_name``; ``None`` if not supported.

    ``priority`` is ``"quality"`` or ``"fps"``. When ``None`` it is read from the
    live ``config.nvidia.dlss.priority`` singleton. An invalid value degrades to
    ``"quality"`` and never raises (the never-hard-fail rule).
    """
    tier_map = _TIERS.get(classify(gpu_name))
    if tier_map is None:
        return None  # unsupported / unknown GPU
    if priority is None:
        priority = _resolve_priority()
    if priority not in tier_map:  # 1A guard: invalid priority -> default, no KeyError
        priority = _DEFAULT_PRIORITY
    letter = tier_map[priority]
    tier = classify(gpu_name)
    return DlssPreset(
        letter=letter,
        value=DLSS_VALUE_BY_LETTER[letter],
        model_name=_MODEL_NAMES[letter],
        tier=tier,
        priority=priority,
    )


def _parse_resolution(at_resolution: str) -> tuple[int, int] | None:
    """Parse a ``"WxH"`` resolution string (e.g. ``"3840x2160"``). ``None`` if unparseable."""
    if not at_resolution or "x" not in at_resolution.lower():
        return None
    try:
        w, h = at_resolution.lower().split("x", 1)
        return int(w.strip()), int(h.strip())
    except (ValueError, AttributeError):
        return None


def monitor_aware_priority(display: dict[str, Any] | None) -> str | None:
    """Smart default priority from the primary display, or ``None`` ("either").

    Rules, evaluated IN ORDER:
      * ``refresh <= 60`` Hz -> ``"quality"`` (no FPS headroom worth chasing)
      * resolution ``>= 4K`` -> ``"quality"`` (premium visual target)
      * otherwise (1440p / sub-4K high-refresh) -> ``None`` ("either"; toggle decides)

    Returns ``None`` on missing / empty / malformed display data (caller falls
    through to the config default). Mirrors ``_get_primary_refresh_hz``'s field set.
    """
    if not isinstance(display, dict) or display.get("error"):
        return None
    refresh = max(
        int(display.get("max_refresh_hz") or 0),
        int(display.get("current_refresh_hz") or 0),
    )
    if 0 < refresh <= 60:
        return "quality"
    res = _parse_resolution(display.get("at_resolution", ""))
    if res is not None:
        w, h = res
        if w >= 3840 or h >= 2160:  # 4K UHD (or wider/taller)
            return "quality"
    return None


def resolve_startup_priority(specs: dict, manual: str | None) -> str:
    """Resolve the priority to seed at GUI startup.

    Precedence: manual (QSettings) > monitor-aware (primary display) >
    lil_bro_config.json default > ``"quality"``. Returns a valid priority string.
    """
    if manual in _VALID_PRIORITIES:
        return manual  # type: ignore[return-value]
    displays = specs.get("DisplayCapabilities") or []
    primary = displays[0] if isinstance(displays, list) and displays else None
    auto = monitor_aware_priority(primary)
    if auto in _VALID_PRIORITIES:
        return auto  # type: ignore[return-value]
    return _resolve_priority()
