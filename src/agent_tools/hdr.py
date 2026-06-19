"""HDR optimization analyzer — pure, no system calls.

Reads pre-collected HDR data (``specs["HDRStatus"]``), the NVIDIA GPU model
(``specs["NVIDIA"]``), and the NVIDIA driver-profile state
(``specs["NVIDIAProfile"]``) and produces a single, hardware-aware
recommendation. v1 is DETECTION-ONLY: the card recommends and deep-links;
no system writes (the Auto HDR / RTX HDR one-click writes are TODOS T-039/T-040).

Priority ladder (single source of truth for the analyzer, the InfoMarker hint,
and the mock fixtures):

    RTX HDR  >  Windows Auto HDR  >  base Windows HDR

    ┌─ HDR-capable panel? ─ no ─→ not_applicable (card hidden upstream is the
    │                              "undetermined" case; this is "panel can't HDR")
    │  yes
    ├─ HDR enabled in Windows? ─ no ─→ hdr_off  (recommend: turn HDR on)
    │  yes
    └─ best path for this hardware already on?
         RTX 20/30/40/50 present → RTX HDR   (on → optimal, off → recommend)
         else Windows 11         → Auto HDR  (on → optimal, off → recommend)
         else (Win10, no RTX)    → base HDR  (already on → optimal)

RTX HDR and Auto HDR are mutually exclusive (RTX HDR replaces Auto HDR), which
is why one card surfaces one recommendation rather than a menu.
"""

from __future__ import annotations

import re
from enum import Enum

# ── Priority ladder (shared constant — D7) ───────────────────────────────────


class HDRTier(str, Enum):
    RTX_HDR = "rtx_hdr"
    AUTO_HDR = "auto_hdr"
    BASE_HDR = "base_hdr"


#: Highest-priority first. The InfoMarker hint and mock fixtures derive their
#: ordering from this tuple so the three never drift.
HDR_PRIORITY: tuple[HDRTier, ...] = (HDRTier.RTX_HDR, HDRTier.AUTO_HDR, HDRTier.BASE_HDR)

#: Per-tier human copy. ``hint`` is the one-liner the InfoMarker ladder renders;
#: ``recommend`` is the card/proposal message when that tier is the pick.
HDR_TIER_COPY: dict[HDRTier, dict[str, str]] = {
    HDRTier.RTX_HDR: {
        "label": "RTX HDR",
        "hint": "RTX HDR (NVIDIA RTX cards)",
        "recommend": (
            "Your RTX card supports RTX HDR — the best-looking SDR to HDR for games. "
            "Turn it on in the NVIDIA app."
        ),
    },
    HDRTier.AUTO_HDR: {
        "label": "Auto HDR",
        "hint": "Windows Auto HDR",
        "recommend": (
            "Your monitor supports HDR but Auto HDR is off — converts SDR games to HDR"
            ". Turn on Auto HDR in Windows HDR settings."
        ),
    },
    HDRTier.BASE_HDR: {
        "label": "Windows HDR",
        "hint": "Turn on HDR in Windows first",
        "recommend": (
            "Your monitor supports HDR, but it's turned off. This will enable HDR in Windows "
            "and allow RTX HDR or Auto HDR."
        ),
    },
}

#: Deep-link targets the card knows how to open.
HDR_SETTINGS_URI = "ms-settings:display"  # Windows display/HDR page
NVIDIA_APP_LINK = "nvidia_app"  # sentinel — card launches the NVIDIA app best-effort

WIN11_MIN_BUILD = 22000


def hdr_priority_hint_lines() -> list[str]:
    """The ordered ladder lines for the InfoMarker '?' hint (derived from the
    shared constant so the hint can never disagree with the analyzer)."""
    return [f"{i}. {HDR_TIER_COPY[t]['hint']}" for i, t in enumerate(HDR_PRIORITY, 1)]


# ── GPU model parsing ─────────────────────────────────────────────────────────


def parse_nvidia_gpu(product_name: str | None) -> dict:
    """Parse an nvidia-smi product name into RTX-tier facts.

    "NVIDIA GeForce RTX 4070" -> {is_rtx: True, model: 4070, series: 40, low_tier: False}
    "NVIDIA GeForce RTX 3050" -> {is_rtx: True, model: 3050, series: 30, low_tier: True}
    "NVIDIA GeForce GTX 1080" -> {is_rtx: False, ...}

    ``low_tier`` (xx50/xx60) flags cards where RTX HDR's per-frame DNN cost is
    least worth it — used to append an FPS-cost note, not to demote the tier.
    """
    out = {"is_rtx": False, "model": 0, "series": 0, "low_tier": False}
    if not product_name:
        return out
    m = re.search(r"RTX\s*(\d{4})", product_name, re.IGNORECASE)
    if not m:
        return out
    model = int(m.group(1))
    series = (model // 1000) * 10  # 4070 -> 40, 5070 -> 50, 2060 -> 20
    out.update(
        is_rtx=series in (20, 30, 40, 50),
        model=model,
        series=series,
        low_tier=(model % 100) <= 60,  # xx50 / xx60 tier
    )
    return out


def _first_rtx_gpu(specs: dict) -> dict | None:
    """Return the parsed-GPU dict for the first RTX GPU in ``specs["NVIDIA"]``,
    or None. ``get_nvidia_smi`` yields a list of {"GPU": product_name, ...}."""
    nvidia = specs.get("NVIDIA")
    if not isinstance(nvidia, list):
        return None
    for gpu in nvidia:
        parsed = parse_nvidia_gpu(gpu.get("GPU") if isinstance(gpu, dict) else None)
        if parsed["is_rtx"]:
            parsed["product_name"] = gpu.get("GPU")
            return parsed
    return None


# ── Display selection (multi-monitor — outside-voice #6) ─────────────────────


def _select_target_display(displays: list[dict]) -> tuple[dict | None, bool]:
    """Pick the display the recommendation is about.

    Prefer the OS-primary if it is HDR-capable. Otherwise, if a *non-primary*
    display is HDR-capable, surface that one (so an HDR secondary + SDR primary
    setup never makes the HDR panel invisible). Returns (display, on_non_primary).
    """
    if not displays:
        return None, False
    primary = next((d for d in displays if d.get("is_primary")), displays[0])
    if primary.get("hdr_capable"):
        return primary, False
    capable = next((d for d in displays if d.get("hdr_capable")), None)
    if capable is not None:
        return capable, True
    return primary, False


# ── Main analyzer ─────────────────────────────────────────────────────────────


def analyze_hdr(specs: dict) -> dict:
    """Pure analyzer. Returns a standardized finding dict.

    ``determined=False`` signals the dashboard to HIDE the card (HDR capability
    couldn't be read — DisplayConfig failed or only a WMI-sourced display
    exists). ``state`` drives card rendering; ``recommended_tier`` names the
    best path; ``can_auto_fix`` is always False in v1 (detection-only).
    """
    base = {
        "check": "hdr",
        "determined": False,
        "status": "HIDDEN",
        "state": "hidden",
        "recommended_tier": None,
        "message": "",
        "deep_link": None,
        "fps_note": False,
        "can_auto_fix": False,
        "primary_device": None,
        "gpu_model": None,
        "on_non_primary": False,
    }

    hdr = specs.get("HDRStatus")
    if not isinstance(hdr, dict) or not hdr.get("determined"):
        # Collector couldn't determine HDR capability — card stays hidden.
        base["error"] = (hdr or {}).get("error") if isinstance(hdr, dict) else "no HDRStatus"
        return base

    displays = hdr.get("displays") or []
    target, on_non_primary = _select_target_display(displays)
    base["determined"] = True
    base["on_non_primary"] = on_non_primary
    base["primary_device"] = (target or {}).get("device")

    # No HDR-capable panel anywhere → nothing to recommend.
    if target is None or not target.get("hdr_capable"):
        return {
            **base,
            "status": "NA",
            "state": "not_applicable",
            "message": "No HDR-capable display detected.",
        }

    # HDR-capable but HDR is off in Windows → recommend turning HDR on (prereq).
    if not target.get("hdr_enabled"):
        return {
            **base,
            "status": "WARNING",
            "state": "hdr_off",
            "recommended_tier": HDRTier.BASE_HDR.value,
            "message": HDR_TIER_COPY[HDRTier.BASE_HDR]["recommend"],
            "deep_link": HDR_SETTINGS_URI,
        }

    # HDR is on — pick the best path for this hardware.
    rtx = _first_rtx_gpu(specs)
    is_win11 = bool(hdr.get("is_win11"))

    if rtx is not None:
        rtx_on = bool((specs.get("NVIDIAProfile") or {}).get("rtx_hdr_enabled"))
        base["gpu_model"] = rtx.get("product_name")
        if rtx_on:
            return {
                **base,
                "status": "OK",
                "state": "optimal",
                "recommended_tier": HDRTier.RTX_HDR.value,
                "message": "RTX HDR is on — your games are getting the best HDR.",
            }
        return {
            **base,
            "status": "WARNING",
            "state": "suboptimal",
            "recommended_tier": HDRTier.RTX_HDR.value,
            "message": HDR_TIER_COPY[HDRTier.RTX_HDR]["recommend"],
            "deep_link": NVIDIA_APP_LINK,
            "fps_note": rtx["low_tier"],
        }

    if is_win11:
        auto_on = bool(hdr.get("auto_hdr_enabled"))
        if auto_on:
            return {
                **base,
                "status": "OK",
                "state": "optimal",
                "recommended_tier": HDRTier.AUTO_HDR.value,
                "message": "Auto HDR is on — your SDR games get an HDR upgrade.",
            }
        return {
            **base,
            "status": "WARNING",
            "state": "suboptimal",
            "recommended_tier": HDRTier.AUTO_HDR.value,
            "message": HDR_TIER_COPY[HDRTier.AUTO_HDR]["recommend"],
            "deep_link": HDR_SETTINGS_URI,
        }

    # Windows 10, no RTX: HDR is on and there's no Auto/RTX path — already best.
    return {
        **base,
        "status": "OK",
        "state": "optimal",
        "recommended_tier": HDRTier.BASE_HDR.value,
        "message": "HDR is on. Auto HDR needs Windows 11; RTX HDR needs an RTX card.",
    }


def hdr_card_visible(finding: dict) -> bool:
    """Whether the dashboard should show the HDR card for this finding.

    Hidden when HDR capability is undetermined (``determined=False`` — the card
    would be a black hole) or when no HDR-capable panel exists (nothing to
    recommend). Shown for the actionable/positive states.
    """
    return bool(finding.get("determined")) and finding.get("state") in (
        "hdr_off",
        "suboptimal",
        "optimal",
    )
