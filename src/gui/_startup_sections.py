"""Fix-dispatch check name → spec section mapping for the Dashboard.

Extracted from ``startup_coordinator`` so the dashboard-refresh logic can import
the map from a leaf module without pulling in the whole coordinator -- this
avoids a circular import once that logic lives in a sibling mixin module.
``startup_coordinator`` re-exports both names for backward-compatible imports
(``tests`` + ``pipeline_controller``).
"""

from __future__ import annotations


# Maps a fix-dispatch check name (the @register_fix key in fix_dispatch.py) to the
# spec sections its card reads. Used to scope the post-apply dashboard re-collect to
# only what changed this session. Any NEW dashboard fix card must extend this map.
_FIX_TO_SECTIONS: dict[str, set[str]] = {
    "display": {"DisplayCapabilities", "HDRStatus"},
    "nvidia_profile": {"NVIDIA", "NVIDIAProfile"},
    "nvidia_dlss_preset": {"NVIDIA", "NVIDIAProfile"},
    "power_plan": {"PowerPlan"},
    "game_mode": {"GameMode"},
    "hags": {"HAGS"},
    # temp_folders has no dashboard card -> no section to refresh.
}


def _sections_for_fixes(fix_keys) -> set[str]:
    """Union the fix->section map over an iterable of fix-dispatch check names."""
    out: set[str] = set()
    for key in fix_keys:
        out |= _FIX_TO_SECTIONS.get(key, set())
    return out
