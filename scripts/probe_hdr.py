"""Dev-only HDR hardware probe — run on a real Win11 + HDR (+ RTX) rig.

NOT bundled (no lil_bro.spec entry). Read-only. It drives the SAME production
read helpers the card uses (src/collectors/sub/hdr_dumper.py +
get_nvidia_profile), so a clean run here means the production detection path
works on this hardware — the gate (D2/D5) before the deferred Auto HDR / RTX HDR
WRITE paths (TODOS T-039 / T-040) are trusted.

Usage (repo root, venv active):

    python scripts/probe_hdr.py

What to capture and check:
  1. DisplayConfig advanced-color per display — is each panel's HDR
     capable/enabled state correct? (confirms the ctypes structs marshalled and
     the type-9 GET_ADVANCED_COLOR_INFO works on this build; if every display
     shows capable=False on a known-HDR panel, this build may need _INFO_2).
  2. Windows build — is_win11 must be True on Win11 (confirms the registry
     CurrentBuildNumber read, not the PyInstaller-capped getwindowsversion).
  3. Auto HDR — the EXACT DirectXUserGlobalSettings string + any per-exe
     override value names. Toggle Auto HDR in Settings and re-run to see the
     before/after delta (drives the T-039 set_auto_hdr_token write + whether
     SwapEffectUpgradeEnable flips alongside AutoHDREnable).
  4. RTX HDR flags — with RTX HDR enabled via the NVIDIA app, re-run and check
     which of the 4 community flags are actually present/set (settles the
     repo-says-2 vs wild-says-4 question for the T-040 write).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Production read helpers — the probe is a thin harness around them (D5).
from src.collectors.sub.hdr_dumper import get_hdr_status, parse_auto_hdr  # noqa: E402

# The 4 RTX HDR driver flags (repo XML documents the first two; the NvTrueHDR
# community recipe also requires the last two — confirm on hardware for T-040).
_RTX_HDR_FLAGS = {
    0x00DD48FB: "RTX HDR - Enable",
    0x00432F84: "RTX HDR - Driver Flags",
    0x00980896: "Game Filters enable (wild recipe)",
    0x1077A11A: "Unknown/required (wild recipe)",
}


def _section(title: str) -> None:
    print("\n" + "=" * 64 + f"\n{title}\n" + "=" * 64)


def probe_displayconfig_and_auto_hdr() -> None:
    _section("1-3. DisplayConfig HDR + Windows build + Auto HDR (production path)")
    status = get_hdr_status()
    print(f"determined        : {status['determined']}")
    if status.get("error"):
        print(f"error             : {status['error']}")
    print(f"os_build          : {status['os_build']}  (is_win11={status['is_win11']})")
    print(f"auto_hdr_enabled  : {status['auto_hdr_enabled']}")
    print(f"per_app_overrides : {status['has_per_app_overrides']}")
    print(f"auto_hdr_raw      : {status['auto_hdr_raw']!r}")
    print(f"  parsed AutoHDREnable -> {parse_auto_hdr(status['auto_hdr_raw'])}")
    print("displays:")
    for d in status["displays"]:
        print(f"  {d['device']:14s} primary={d['is_primary']!s:5s} "
              f"hdr_capable={d['hdr_capable']!s:5s} hdr_enabled={d['hdr_enabled']!s:5s} "
              f"({d['source']})")


def probe_auto_hdr_raw_registry() -> None:
    """Detailed registry dump for the T-039 write design (every value name)."""
    _section("Auto HDR registry detail (HKCU UserGpuPreferences) — for T-039")
    import winreg

    key_path = r"Software\Microsoft\DirectX\UserGpuPreferences"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            _, count, _ = winreg.QueryInfoKey(key)
            if not count:
                print("(key exists but has no values — Auto HDR never set globally)")
            for idx in range(count):
                name, data, _ = winreg.EnumValue(key, idx)
                tag = "  <- global default" if name == "DirectXUserGlobalSettings" else "  <- per-exe override"
                print(f"  {name!r} = {data!r}{tag}")
    except FileNotFoundError:
        print("(UserGpuPreferences key does not exist — no graphics prefs set yet)")


def probe_rtx_hdr_flags() -> None:
    _section("4. RTX HDR driver flags (NVIDIAProfile export) — for T-040")
    from src.collectors.sub.nvidia_profile_dumper import get_nvidia_profile

    try:
        prof = get_nvidia_profile()
    except OSError as exc:
        print(f'NVIDIA profile read failed: {exc}')
        if 'elevation' in str(exc).lower():
            print('  (NPI export needs elevation - re-run this probe from an elevated shell.)')
        return
    if not prof.get("available"):
        print(f"NVIDIA profile unavailable: {prof.get('reason') or prof.get('error')}")
        return
    if prof.get("error"):
        print(f"NPI export error: {prof['error']}")
        return
    print(f"rtx_hdr_enabled (interpreted) : {prof.get('rtx_hdr_enabled')}")
    raw = prof.get("raw_settings") or {}
    print("flag presence in the exported Base Profile:")
    for sid, label in _RTX_HDR_FLAGS.items():
        if sid in raw:
            print(f"  0x{sid:08X} {label:38s} = {raw[sid]}  (0x{raw[sid]:X})")
        else:
            print(f"  0x{sid:08X} {label:38s} = <absent>")


def main() -> int:
    print("lil_bro HDR hardware probe — read-only, no system changes.")
    try:
        probe_displayconfig_and_auto_hdr()
        probe_auto_hdr_raw_registry()
        probe_rtx_hdr_flags()
    except Exception as exc:  # dev tool — surface the full failure
        import traceback
        print(f"\nPROBE FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1
    print("\nDone. Capture this output (and a before/after across a Settings"
          " Auto HDR toggle / NVIDIA-app RTX HDR enable) before the T-039/T-040 writes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
