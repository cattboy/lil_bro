# Plan: Fix NVIDIA Profile Inspector Setting Misconfigurations

   ## Summary

   Fix a silent bug where the power_mgmt setting ID points to a non-existent NPI setting (0x10555C28), causing power management analysis and fixes to always fail silently. Also convert all 15 setting IDs
   from decimal literals to hex literals for readability and maintainability. Add a CLAUDE.md reference entry for the NPI XML.

   ---

   ## Changes

   ### Change 1: Fix power_mgmt hex ID (BUG FIX -- Critical)

   **File:** C:/1_Coding/2026/lil_bro/src/collectors/sub/nvidia_profile_dumper.py
   **Line:** 48

   The current code uses decimal 274029608 (hex 0x10555C28) for the power_mgmt setting ID. This hex value does NOT exist anywhere in the NPI XML reference -- zero grep hits.

   The correct value is 0x1057EB71 (decimal 274197361), confirmed by:
   - docs/NPI_CustomSettingNames.xml line 10165-10166: UserfriendlyName Power Management - Mode with HexSettingID 0x1057EB71
   - docs/NPI_Base_Profile_Export_Example.nip line 69: SettingID 274197361 with SettingNameInfo Power management mode

   The old value was off by 167753 (274197361 - 274029608).

   **Impact of the bug:** Every call to _interpret_power_mgmt(), _check_power_mgmt(), and the setter uses the wrong SettingID. The collector reads the wrong setting (always None), the analyzer compares
   against the wrong setting (always reports misconfigured), and the setter writes to a non-existent setting ID (does nothing).

   **Impact of the fix:** Power management will be correctly read, analyzed, and fixed.

   ---

   ### Change 2: Convert SETTING_IDS from decimal to hex literals (Code Quality)

   **File:** C:/1_Coding/2026/lil_bro/src/collectors/sub/nvidia_profile_dumper.py
   **Lines:** 31-49

   Replace the entire SETTING_IDS dict. Convert all 15 values from decimal integers with hex comments to hex literals with NPI UserfriendlyName comments. This includes the power_mgmt fix from Change 1.

   The new dict block (lines 31-49) should become:

   ```python
   # Canonical setting IDs from docs/NPI_CustomSettingNames.xml.
   # Python hex literals are identical to decimal at runtime -- hex is used
   # for easy cross-referencing with the XML HexSettingID values.
   SETTING_IDS: dict[str, int] = {
       "gsync_global_feature":     0x1094F157,  # GSYNC - Global Feature
       "gsync_global_mode":        0x1094F1F7,  # GSYNC - Global Mode
       "gsync_app_mode":           0x1194F158,  # GSYNC - Application Mode
       "gsync_app_state":          0x10A879CF,  # GSYNC - Application State
       "gsync_app_requested":      0x10A879AC,  # GSYNC - Application Requested State
       "gsync_indicator_overlay":  0x10029538,  # GSYNC - Indicator Overlay
       "gsync_support_indicator":  0x008DF510,  # GSYNC - Support Indicator Overlay
       "vsync":                    0x00A879CF,  # Vertical Sync
       "vsync_tear_control":       0x005A375C,  # Vertical Sync - Tear Control
       "vsync_smooth_afr":         0x101AE763,  # Vertical Sync - Smooth AFR Behavior
       "fps_limiter_v3":           0x10835002,  # Frame Rate Limiter V3
       "rebar_enable":             0x000F00BA,  # rBAR - Enable
       "dlss_preset_profile":      0x00634291,  # DLSS - Forced Model Preset Profile
       "dlss_preset_letter":       0x10E41DF3,  # DLSS - Forced Preset Letter
       "power_mgmt":               0x1057EB71,  # Power Management - Mode
   }
   ```

   **Why this is safe:**
   - Python 0x1094F157 == 278196567 is True -- same int. Zero runtime effect.
   - All consumers reference SETTING_IDS by key name, never by hardcoded decimal.
   - Consumers: nvidia_profile_dumper.py _interpret_* functions, nvidia_profile.py, nvidia_profile_setter.py.

   **Test impact -- NONE:**
   - _SAMPLE_NIP XML in tests (lines 36-62) uses hardcoded decimal SettingIDs (277041154, 11041231, 278196567). These simulate real .nip output. Do NOT change.
   - Lines 118-120, 376, 382, 391, 408, 414-415 use decimal in parse_nip assertions. Correct as-is.
   - Line 308 builds raw via dict comprehension from SETTING_IDS.items() -- propagates automatically.
   - Lines 311, 313 use SETTING_IDS[key_name] -- key-based, safe.

   ---

   ### Change 3: Update CLAUDE.md vendor-supplied docs section

   **File:** C:/1_Coding/2026/lil_bro/CLAUDE.md
   **Lines:** 23-26

   Add NPI_CustomSettingNames.xml reference. Insert after line 26 (cinebench entry):

   ```markdown
   - **docs/NPI_CustomSettingNames.xml** is the canonical reference for all NVIDIA Profile Inspector setting IDs. Cross-reference any SETTING_IDS changes in nvidia_profile_dumper.py against this file
   HexSettingID values.
   ```

   Note: The XML lives in docs/, not docs/vendor-supplied/. The entry references its actual path.

   ---

   ### Change 4: Review _get_gpu_generation (No change needed)

   **File:** C:/1_Coding/2026/lil_bro/src/agent_tools/nvidia_profile.py
   **Lines:** 32-37

   The regex is correct. Matches RTX 4090 to 40, RTX 3080 Ti to 30, RTX 2070 Super to 20, RTX 5080 to 50. Correctly rejects GTX 1080 and AMD GPUs. Data flow verified end-to-end. Tests pass at lines 241-264.

   **No changes required.**

   ---

   ## Implementation Order

   1. **Change 2** (includes Change 1) -- rewrite SETTING_IDS dict in nvidia_profile_dumper.py lines 31-49. One atomic edit.
   2. **Change 3** -- add NPI XML reference to CLAUDE.md after line 26.
   3. **Run tests** -- python -m pytest tests/test_nvidia_profile.py -v

   ## Risk Assessment

   | Change | Risk | Rationale |
   |--------|------|-----------|
   | power_mgmt fix | Zero regression risk | Old ID never matched anything |
   | decimal to hex | Zero runtime risk | Same int values; all key-based access |
   | CLAUDE.md | None | Documentation only |
   | regex review | None | No change needed |

   ## Files Modified

   | File | Type of change |
   |------|---------------|
   | src/collectors/sub/nvidia_profile_dumper.py | Bug fix + readability (lines 31-49) |
   | CLAUDE.md | Documentation (line 27 insert) |

   ## Files NOT Modified (verified correct)

   | File | Reason |
   |------|--------|
   | src/agent_tools/nvidia_profile.py | Imports SETTING_IDS by key; unaffected |
   | src/agent_tools/nvidia_profile_setter.py | Imports SETTING_IDS by key; unaffected |
   | tests/test_nvidia_profile.py | Key-based access and .nip format simulation; unaffected |
   | docs/NPI_CustomSettingNames.xml | Read-only reference |
   