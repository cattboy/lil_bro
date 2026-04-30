"""Tests for NVIDIA Profile Inspector integration.

Covers:
  - Collector: find_npi_exe, parse_nip, get_nvidia_profile
  - Analyzer: analyze_nvidia_profile + all sub-checks
  - Formula: calculate_fps_cap across common Hz values
  - NIP modifier: build_optimized_nip (XML roundtrip)
  - GPU generation detection: _get_gpu_generation + DLSS preset mapping
  - AMD guard: SKIPPED status for AMD-only systems
  - Fixer: fix_nvidia_profile (mocked subprocess)
  - Fix dispatch: nvidia_profile registered + callable
"""

import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ── Shared helpers ────────────────────────────────────────────────────────────

def _make_nip_bytes(text: str) -> bytes:
    """Encode NIP XML string as UTF-16 with BOM."""
    return text.encode("utf-16")


def _write_nip(path: str, text: str):
    Path(path).write_bytes(_make_nip_bytes(text))


_SAMPLE_NIP = """\
<?xml version="1.0" encoding="utf-16"?>
<ArrayOfProfile>
  <Profile>
    <ProfileName>Base Profile</ProfileName>
    <Executeables />
    <Settings>
      <ProfileSetting>
        <SettingNameInfo>Frame Rate Limiter V3</SettingNameInfo>
        <SettingID>277041154</SettingID>
        <SettingValue>225</SettingValue>
        <ValueType>Dword</ValueType>
      </ProfileSetting>
      <ProfileSetting>
        <SettingNameInfo>Vertical Sync</SettingNameInfo>
        <SettingID>11041231</SettingID>
        <SettingValue>0</SettingValue>
        <ValueType>Dword</ValueType>
      </ProfileSetting>
      <ProfileSetting>
        <SettingNameInfo>GSYNC - Global Feature Enable</SettingNameInfo>
        <SettingID>278196567</SettingID>
        <SettingValue>0</SettingValue>
        <ValueType>Dword</ValueType>
      </ProfileSetting>
    </Settings>
  </Profile>
</ArrayOfProfile>"""


def _nvidia_specs(
    gpu_name: str = "NVIDIA GeForce RTX 4090",
    rebar: bool = True,
    refresh_hz: int = 240,
    npi_data: dict | None = None,
) -> dict:
    """Build a minimal specs dict for analyzer tests."""
    if npi_data is None:
        npi_data = {
            "available": True,
            "gsync_enabled": False,
            "vsync_mode": "off",
            "fps_cap": 0,
            "rebar_driver": False,
            "dlss_preset": "A",
            "power_mgmt": "adaptive",
            "raw_settings": {},
        }
    return {
        "NVIDIA": [{"GPU": gpu_name, "ReBAR": rebar}],
        "DisplayCapabilities": [
            {"current_refresh_hz": refresh_hz, "max_refresh_hz": refresh_hz, "edid_declared_max_hz": None}
        ],
        "NVIDIAProfile": npi_data,
    }


# ── 1. find_npi_exe ──────────────────────────────────────────────────────────

class TestFindNpiExe:
    def test_returns_none_when_not_found(self):
        from src.utils.nvidia_npi import find_npi_exe
        import src.utils.nvidia_npi as mod
        with patch.object(mod, "_NPI_SEARCH_PATHS", ["/nonexistent/npi.exe"]):
            assert find_npi_exe() is None

    def test_returns_first_existing_path(self, tmp_path):
        from src.utils.nvidia_npi import find_npi_exe
        import src.utils.nvidia_npi as mod
        exe = tmp_path / "nvidiaProfileInspector.exe"
        exe.write_bytes(b"fake")
        with patch.object(mod, "_NPI_SEARCH_PATHS", [str(exe), "/other/path.exe"]):
            assert find_npi_exe() == str(exe)


# ── 2. parse_nip ─────────────────────────────────────────────────────────────

class TestParseNip:
    def test_parses_utf16_xml(self, tmp_path):
        from src.utils.nip_io import parse_nip
        nip = tmp_path / "test.nip"
        _write_nip(str(nip), _SAMPLE_NIP)
        result = parse_nip(str(nip))
        assert result[277041154] == 225
        assert result[11041231] == 0
        assert result[278196567] == 0

    def test_empty_settings(self, tmp_path):
        from src.utils.nip_io import parse_nip
        xml = """\
<?xml version="1.0" encoding="utf-16"?>
<ArrayOfProfile>
  <Profile>
    <ProfileName>Base Profile</ProfileName>
    <Settings />
  </Profile>
</ArrayOfProfile>"""
        nip = tmp_path / "empty.nip"
        _write_nip(str(nip), xml)
        assert parse_nip(str(nip)) == {}

    def test_skips_non_numeric_values(self, tmp_path):
        from src.utils.nip_io import parse_nip
        xml = """\
<?xml version="1.0" encoding="utf-16"?>
<ArrayOfProfile>
  <Profile>
    <ProfileName>Base Profile</ProfileName>
    <Settings>
      <ProfileSetting>
        <SettingNameInfo>Bogus</SettingNameInfo>
        <SettingID>bad</SettingID>
        <SettingValue>also_bad</SettingValue>
        <ValueType>Dword</ValueType>
      </ProfileSetting>
    </Settings>
  </Profile>
</ArrayOfProfile>"""
        nip = tmp_path / "bad.nip"
        _write_nip(str(nip), xml)
        assert parse_nip(str(nip)) == {}


# ── 3. get_nvidia_profile ────────────────────────────────────────────────────

class TestGetNvidiaProfile:
    def test_unavailable_when_exe_not_found(self):
        from src.collectors.sub.nvidia_profile_dumper import get_nvidia_profile
        import src.collectors.sub.nvidia_profile_dumper as mod
        with patch.object(mod, "find_npi_exe", return_value=None):
            r = get_nvidia_profile()
        assert r["available"] is False
        assert "not found" in r["reason"]

    def test_error_on_timeout(self):
        from src.collectors.sub.nvidia_profile_dumper import get_nvidia_profile
        import src.collectors.sub.nvidia_profile_dumper as mod
        with patch.object(mod, "find_npi_exe", return_value="npi.exe"):
            with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("npi.exe", 15)):
                r = get_nvidia_profile()
        assert r["available"] is True
        assert "timed out" in r["error"]

    def test_error_when_nonzero_returncode(self):
        from src.collectors.sub.nvidia_profile_dumper import get_nvidia_profile
        import src.collectors.sub.nvidia_profile_dumper as mod
        mock_result = MagicMock(returncode=1, stderr=b"error msg")
        with patch.object(mod, "find_npi_exe", return_value="npi.exe"):
            with patch("subprocess.run", return_value=mock_result):
                r = get_nvidia_profile()
        assert "NPI export failed" in r["error"]

    def test_error_when_no_nip_produced(self):
        from src.collectors.sub.nvidia_profile_dumper import get_nvidia_profile
        import src.collectors.sub.nvidia_profile_dumper as mod
        mock_result = MagicMock(returncode=0)
        with patch.object(mod, "find_npi_exe", return_value="npi.exe"):
            with patch("subprocess.run", return_value=mock_result):
                # no .nip files written to tmpdir
                r = get_nvidia_profile()
        assert "no .nip file" in r["error"]

    def test_parses_settings_on_success(self, tmp_path):
        from src.collectors.sub.nvidia_profile_dumper import get_nvidia_profile
        import src.collectors.sub.nvidia_profile_dumper as mod

        def fake_run(cmd, cwd, capture_output, timeout):
            _write_nip(os.path.join(cwd, "profile.nip"), _SAMPLE_NIP)
            return MagicMock(returncode=0)

        with patch.object(mod, "find_npi_exe", return_value="npi.exe"):
            with patch("subprocess.run", side_effect=fake_run):
                r = get_nvidia_profile()

        assert r["available"] is True
        assert "error" not in r
        assert r["fps_cap"] == 225
        assert r["vsync_mode"] == "off"
        assert r["gsync_enabled"] is False


# ── 4. FPS cap formula ───────────────────────────────────────────────────────

class TestCalculateFpsCap:
    @pytest.mark.parametrize("hz,expected", [
        (60,  59),
        (120, 116),
        (144, 139),
        (165, 158),
        (240, 226),
        (360, 328),
        (480, 424),
    ])
    def test_formula(self, hz, expected):
        from src.agent_tools.nvidia_profile import calculate_fps_cap
        assert calculate_fps_cap(hz) == expected


# ── 5. GPU generation detection ──────────────────────────────────────────────

class TestGpuGeneration:
    @pytest.mark.parametrize("gpu_name,expected_gen", [
        ("NVIDIA GeForce RTX 4090", "40"),
        ("NVIDIA GeForce RTX 3080 Ti", "30"),
        ("NVIDIA GeForce RTX 2070 Super", "20"),
        ("NVIDIA GeForce RTX 5080", "50"),
        ("NVIDIA GeForce GTX 1080", None),  # GTX, not RTX
        ("AMD Radeon RX 7900 XTX", None),
    ])
    def test_detect_generation(self, gpu_name, expected_gen):
        from src.agent_tools.nvidia_profile import _get_gpu_generation
        assert _get_gpu_generation(gpu_name) == expected_gen

    @pytest.mark.parametrize("gen,expected_letter", [
        ("50", "L"),
        ("40", "L"),
        ("30", "K"),
        ("20", "K"),
    ])
    def test_dlss_preset_mapping(self, gen, expected_letter):
        from src.agent_tools.nvidia_profile import DLSS_PRESETS
        letter, _ = DLSS_PRESETS[gen]
        assert letter == expected_letter


# ── 6. Analyzer ──────────────────────────────────────────────────────────────

class TestAnalyzeNvidiaProfile:
    def test_skipped_for_amd_gpu(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = {"NVIDIA": [], "AMD": [{"GPU": "Radeon RX 7900 XTX"}], "NVIDIAProfile": {}}
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "SKIPPED"
        assert "AMD" in r["message"]

    def test_skipped_for_no_gpu(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = {"NVIDIA": [], "AMD": [], "NVIDIAProfile": {}}
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "SKIPPED"

    def test_unknown_when_npi_unavailable(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = _nvidia_specs(npi_data={"available": False, "reason": "NPI binary not found"})
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "UNKNOWN"
        assert r["can_auto_fix"] is False

    def test_unknown_when_npi_errored(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = _nvidia_specs(npi_data={"available": True, "error": "export failed"})
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "UNKNOWN"

    def test_warning_when_settings_not_optimal(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = _nvidia_specs()  # All defaults are suboptimal
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "WARNING"
        assert r["can_auto_fix"] is True
        assert "sub_findings" in r

    def test_ok_when_all_settings_optimal(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        from src.utils.nvidia_npi import SETTING_IDS, TARGET_VALUES

        # Build optimal raw_settings: all target values present
        raw = {sid: TARGET_VALUES[key] for key, sid in SETTING_IDS.items()
               if key in TARGET_VALUES}
        # Add correct FPS cap for 240Hz
        raw[SETTING_IDS["fps_limiter_v3"]] = 226  # calculate_fps_cap(240)
        # Add correct DLSS for RTX 40-series: Preset L = 0x0C = 12
        raw[SETTING_IDS["dlss_preset_letter"]] = 0x0C

        npi_data = {
            "available": True,
            "gsync_enabled": True,
            "vsync_mode": "force_on",
            "fps_cap": 226,
            "rebar_driver": True,
            "dlss_preset": "L",
            "power_mgmt": "max_performance",
            "raw_settings": raw,
        }
        specs = _nvidia_specs(npi_data=npi_data, rebar=True, refresh_hz=240)
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "OK"
        assert r["can_auto_fix"] is False

    def test_handles_json_round_tripped_raw_settings(self):
        """Specs reloaded from full_specs.json have str-keyed raw_settings; the checker must normalize keys."""
        import json
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        from src.utils.nvidia_npi import SETTING_IDS, TARGET_VALUES

        raw = {sid: TARGET_VALUES[key] for key, sid in SETTING_IDS.items()
               if key in TARGET_VALUES}
        raw[SETTING_IDS["fps_limiter_v3"]] = 226
        raw[SETTING_IDS["dlss_preset_letter"]] = 0x0C

        npi_data = {
            "available": True,
            "gsync_enabled": True,
            "vsync_mode": "force_on",
            "fps_cap": 226,
            "rebar_driver": True,
            "dlss_preset": "L",
            "power_mgmt": "max_performance",
            "raw_settings": raw,
        }
        specs = _nvidia_specs(npi_data=npi_data, rebar=True, refresh_hz=240)
        # Round-trip through JSON: int keys in raw_settings become strings.
        specs = json.loads(json.dumps(specs, default=str))
        r = analyze_nvidia_profile(specs)
        assert r["status"] == "OK", r

    def test_rebar_driver_skipped_when_bios_rebar_off(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = _nvidia_specs(rebar=False)
        r = analyze_nvidia_profile(specs)
        # ReBar driver sub-finding should be skipped (BIOS ReBar off)
        rebar_sub = next(s for s in r.get("sub_findings", []) if s["name"] == "ReBar Driver")
        assert rebar_sub.get("skipped") is True

    def test_dlss_skipped_for_gtx_gpu(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        specs = _nvidia_specs(gpu_name="NVIDIA GeForce GTX 1080")
        r = analyze_nvidia_profile(specs)
        dlss_sub = next(s for s in r.get("sub_findings", []) if s["name"] == "DLSS Preset")
        assert dlss_sub.get("skipped") is True

    def test_fps_cap_skipped_when_no_display_data(self):
        from src.agent_tools.nvidia_profile import analyze_nvidia_profile
        npi_data = {
            "available": True,
            "gsync_enabled": False,
            "vsync_mode": "off",
            "fps_cap": 0,
            "rebar_driver": False,
            "dlss_preset": "A",
            "power_mgmt": "adaptive",
            "raw_settings": {},
        }
        specs = {
            "NVIDIA": [{"GPU": "NVIDIA GeForce RTX 4090", "ReBAR": True}],
            "DisplayCapabilities": [],  # No display data
            "NVIDIAProfile": npi_data,
        }
        r = analyze_nvidia_profile(specs)
        fps_sub = next(s for s in r.get("sub_findings", []) if s["name"] == "FPS Cap")
        assert fps_sub.get("skipped") is True


# ── 7. NIP XML modifier ──────────────────────────────────────────────────────

class TestBuildOptimizedNip:
    def test_modifies_existing_setting(self, tmp_path):
        from src.agent_tools.nvidia_profile_setter import build_optimized_nip
        src_nip = str(tmp_path / "source.nip")
        _write_nip(src_nip, _SAMPLE_NIP)

        # Set FPS limiter to 226
        target = {277041154: 226}
        out_path = build_optimized_nip(src_nip, target)

        try:
            from src.utils.nip_io import parse_nip
            result = parse_nip(out_path)
            assert result[277041154] == 226
        finally:
            os.unlink(out_path)

    def test_adds_new_setting_when_not_present(self, tmp_path):
        from src.agent_tools.nvidia_profile_setter import build_optimized_nip
        src_nip = str(tmp_path / "source.nip")
        _write_nip(src_nip, _SAMPLE_NIP)

        new_sid = 983226  # rebar_enable -- not in SAMPLE_NIP
        target = {new_sid: 1}
        out_path = build_optimized_nip(src_nip, target)

        try:
            from src.utils.nip_io import parse_nip
            result = parse_nip(out_path)
            assert result[new_sid] == 1
        finally:
            os.unlink(out_path)

    def test_preserves_unmodified_settings(self, tmp_path):
        from src.agent_tools.nvidia_profile_setter import build_optimized_nip
        src_nip = str(tmp_path / "source.nip")
        _write_nip(src_nip, _SAMPLE_NIP)

        # Only change VSync -- fps limiter should stay 225
        target = {11041231: 0x47814940}
        out_path = build_optimized_nip(src_nip, target)

        try:
            from src.utils.nip_io import parse_nip
            result = parse_nip(out_path)
            assert result[277041154] == 225   # unchanged
            assert result[11041231] == 0x47814940  # changed
        finally:
            os.unlink(out_path)

    def test_output_is_utf16(self, tmp_path):
        from src.agent_tools.nvidia_profile_setter import build_optimized_nip
        src_nip = str(tmp_path / "source.nip")
        _write_nip(src_nip, _SAMPLE_NIP)

        out_path = build_optimized_nip(src_nip, {})
        try:
            raw = Path(out_path).read_bytes()
            # UTF-16 files start with BOM: FF FE (LE) or FE FF (BE)
            assert raw[:2] in (b"\xff\xfe", b"\xfe\xff")
        finally:
            os.unlink(out_path)

    def test_raises_on_no_profiles(self, tmp_path):
        from src.agent_tools.nvidia_profile_setter import build_optimized_nip
        empty = """\
<?xml version="1.0" encoding="utf-16"?>
<ArrayOfProfile />"""
        src_nip = str(tmp_path / "no_profiles.nip")
        _write_nip(src_nip, empty)
        with pytest.raises(ValueError, match="No profiles"):
            build_optimized_nip(src_nip, {})


# ── 8. Fixer: fix_nvidia_profile ─────────────────────────────────────────────

class TestFixNvidiaProfile:
    def _make_specs(self, rebar: bool = True, hz: int = 240, gpu: str = "NVIDIA GeForce RTX 4090") -> dict:
        return {
            "NVIDIA": [{"GPU": gpu, "ReBAR": rebar}],
            "DisplayCapabilities": [
                {"current_refresh_hz": hz, "max_refresh_hz": hz, "edid_declared_max_hz": None}
            ],
        }

    @patch("src.agent_tools.nvidia_profile_setter.apply_nvidia_profile", return_value=(True, "OK"))
    @patch("src.agent_tools.nvidia_profile_setter.build_optimized_nip")
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="/backup/nv.nip")
    @patch("src.agent_tools.nvidia_profile_setter.export_current_profile")
    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value="npi.exe")
    def test_success(self, mock_find, mock_export, mock_backup, mock_build, mock_apply, tmp_path):
        mock_export.return_value = (str(tmp_path / "profile.nip"), {})
        mock_build.return_value = str(tmp_path / "modified.nip")
        # Create the modified nip so unlink works
        Path(str(tmp_path / "modified.nip")).write_bytes(b"x")

        from src.agent_tools.nvidia_profile_setter import fix_nvidia_profile
        result = fix_nvidia_profile(self._make_specs())
        assert result is True
        mock_apply.assert_called_once()

    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value=None)
    def test_raises_when_exe_not_found(self, mock_find):
        from src.agent_tools.nvidia_profile_setter import fix_nvidia_profile
        with pytest.raises(FileNotFoundError):
            fix_nvidia_profile({})

    @patch("src.agent_tools.nvidia_profile_setter.apply_nvidia_profile", return_value=(False, "NPI failed"))
    @patch("src.agent_tools.nvidia_profile_setter.build_optimized_nip")
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="/backup/nv.nip")
    @patch("src.agent_tools.nvidia_profile_setter.export_current_profile")
    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value="npi.exe")
    def test_raises_on_import_failure(self, mock_find, mock_export, mock_backup, mock_build, mock_apply, tmp_path):
        mock_export.return_value = (str(tmp_path / "profile.nip"), {})
        mock_build.return_value = str(tmp_path / "modified.nip")
        Path(str(tmp_path / "modified.nip")).write_bytes(b"x")

        from src.agent_tools.nvidia_profile_setter import fix_nvidia_profile
        from src.utils.errors import SetterError
        with pytest.raises(SetterError, match="Profile import failed"):
            fix_nvidia_profile(self._make_specs())


# ── 9. Fix dispatch ──────────────────────────────────────────────────────────

class TestFixDispatchNvidiaProfile:
    def test_nvidia_profile_registered(self):
        from src.pipeline.fix_dispatch import FIX_REGISTRY
        assert "nvidia_profile" in FIX_REGISTRY
        assert callable(FIX_REGISTRY["nvidia_profile"])

    def test_all_expected_checks_registered(self):
        from src.pipeline.fix_dispatch import FIX_REGISTRY
        expected = {"display", "power_plan", "temp_folders", "game_mode", "nvidia_profile"}
        assert set(FIX_REGISTRY.keys()) == expected

    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="/backup.nip")
    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    @patch("src.agent_tools.nvidia_profile_setter.fix_nvidia_profile", return_value=True)
    def test_dispatch_success(self, mock_fix, mock_find, mock_backup):
        from src.pipeline.fix_dispatch import execute_fix
        assert execute_fix("nvidia_profile", {}) is True

    @patch("src.agent_tools.nvidia_profile_setter.fix_nvidia_profile",
           side_effect=FileNotFoundError("npi not found"))
    def test_dispatch_file_not_found(self, mock_fix):
        from src.pipeline.fix_dispatch import execute_fix
        assert execute_fix("nvidia_profile", {}) is False

    @patch("src.agent_tools.nvidia_profile_setter.fix_nvidia_profile",
           side_effect=RuntimeError("import failed"))
    def test_dispatch_runtime_error(self, mock_fix):
        from src.pipeline.fix_dispatch import execute_fix
        assert execute_fix("nvidia_profile", {}) is False

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.nvidia_profile_setter.fix_nvidia_profile", return_value=True)
    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="/backup.nip")
    def test_dispatch_manifest_entry_captured(self, mock_backup, mock_find, mock_fix, mock_append):
        """Manifest entry written with backup path after successful dispatch."""
        from src.pipeline.fix_dispatch import execute_fix
        assert execute_fix("nvidia_profile", {}) is True
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][0]
        assert entry["fix"] == "nvidia_profile"
        assert entry["revertible"] is True
        assert entry["before_backup"] == "/backup.nip"


# ── 10. LLM fallback template ────────────────────────────────────────────────

class TestActionProposerNvidiaProfile:
    def test_fallback_template_exists(self):
        from src.llm.action_proposer import _FALLBACK
        assert "nvidia_profile" in _FALLBACK
        t = _FALLBACK["nvidia_profile"]
        assert t["can_auto_fix"] is True
        assert t["severity"] == "HIGH"

    def test_build_llm_input_includes_nvidia_profile(self):
        from src.llm.action_proposer import build_llm_input
        findings = [{
            "check": "nvidia_profile",
            "status": "WARNING",
            "message": "Profile not optimized",
            "can_auto_fix": True,
            "current": {"gpu_model": "RTX 4090"},
            "sub_findings": [
                {"name": "G-Sync", "ok": False},
                {"name": "VSync", "ok": False},
            ],
        }]
        result = build_llm_input({"cpu": "i9-14900K"}, findings)
        npi_entry = next((f for f in result["findings"] if f["check"] == "nvidia_profile"), None)
        assert npi_entry is not None
        assert npi_entry["gpu_model"] == "RTX 4090"
        assert "G-Sync" in npi_entry["missing_optimizations"]
        assert "VSync" in npi_entry["missing_optimizations"]

    def test_build_fallback_returns_nvidia_template(self):
        from src.llm.action_proposer import _build_fallback
        findings = [{"check": "nvidia_profile", "status": "WARNING"}]
        proposals = _build_fallback(findings)
        assert len(proposals) == 1
        assert proposals[0]["finding"] == "nvidia_profile"



# ── 10. wait_for_nip_ready ───────────────────────────────────────────────────

class TestWaitForNipReady:
    def test_passes_on_valid_sample(self, tmp_path):
        from src.utils.nip_io import wait_for_nip_ready
        nip = tmp_path / "valid.nip"
        _write_nip(str(nip), _SAMPLE_NIP)
        wait_for_nip_ready(str(nip), timeout=2.0, poll_interval=0.05)

    def test_tolerates_trailing_whitespace(self, tmp_path):
        from src.utils.nip_io import wait_for_nip_ready
        nip = tmp_path / "trail.nip"
        # Append CRLF after closing tag (common on Windows)
        nip.write_bytes((_SAMPLE_NIP + "\r\n").encode("utf-16"))
        wait_for_nip_ready(str(nip), timeout=2.0, poll_interval=0.05)

    def test_raises_on_missing_bom(self, tmp_path):
        from src.utils.nip_io import wait_for_nip_ready
        from src.utils.errors import SetterError
        nip = tmp_path / "nobom.nip"
        # UTF-16-LE body without BOM
        nip.write_bytes(_SAMPLE_NIP.encode("utf-16-le"))
        with pytest.raises(SetterError, match="not ready"):
            wait_for_nip_ready(str(nip), timeout=0.5, poll_interval=0.05)

    def test_raises_on_odd_byte_count(self, tmp_path):
        from src.utils.nip_io import wait_for_nip_ready
        from src.utils.errors import SetterError
        nip = tmp_path / "odd.nip"
        # Valid bytes but odd length (truncated UTF-16)
        data = _SAMPLE_NIP.encode("utf-16")[:-1]
        nip.write_bytes(data)
        with pytest.raises(SetterError, match="not ready"):
            wait_for_nip_ready(str(nip), timeout=0.5, poll_interval=0.05)

    def test_raises_when_tail_missing_close_bracket(self, tmp_path):
        from src.utils.nip_io import wait_for_nip_ready
        from src.utils.errors import SetterError
        nip = tmp_path / "midtag.nip"
        # Strip the final `>` (and its UTF-16 low byte) to simulate mid-tag flush
        full = _SAMPLE_NIP.encode("utf-16")
        nip.write_bytes(full[:-2])
        with pytest.raises(SetterError, match="not ready"):
            wait_for_nip_ready(str(nip), timeout=0.5, poll_interval=0.05)

    def test_raises_on_missing_file(self, tmp_path):
        from src.utils.nip_io import wait_for_nip_ready
        from src.utils.errors import SetterError
        with pytest.raises(SetterError, match="not ready"):
            wait_for_nip_ready(str(tmp_path / "ghost.nip"), timeout=0.3, poll_interval=0.05)

    def test_raises_when_file_keeps_growing(self, tmp_path):
        """Writer that never settles should time out (size-stable check)."""
        import threading
        import time
        from src.utils.nip_io import wait_for_nip_ready
        from src.utils.errors import SetterError

        nip = tmp_path / "growing.nip"
        full = _SAMPLE_NIP.encode("utf-16")
        stop = threading.Event()

        def writer():
            # Keep writing a valid-looking file but append junk every tick
            # so size never stabilizes.
            extra = b""
            while not stop.is_set():
                nip.write_bytes(full + extra)
                extra += b"\x20\x00"  # append a UTF-16 space
                time.sleep(0.03)

        t = threading.Thread(target=writer, daemon=True)
        t.start()
        try:
            with pytest.raises(SetterError, match="not ready"):
                wait_for_nip_ready(str(nip), timeout=0.4, poll_interval=0.05)
        finally:
            stop.set()
            t.join(timeout=1.0)


# ── 11. parse_nip_with_retry ─────────────────────────────────────────────────

class TestParseNipRetry:
    def test_succeeds_on_first_attempt(self, tmp_path):
        from src.utils.nip_io import parse_nip_with_retry
        nip = tmp_path / "ok.nip"
        _write_nip(str(nip), _SAMPLE_NIP)
        result = parse_nip_with_retry(str(nip))
        assert result[277041154] == 225

    def test_retries_then_succeeds(self, tmp_path, monkeypatch):
        from src.utils import nip_io
        calls = {"n": 0}

        def flaky(path):
            calls["n"] += 1
            if calls["n"] == 1:
                raise UnicodeDecodeError("utf-16-le", b"", 0, 1, "truncated data")
            return {42: 100}

        monkeypatch.setattr("src.utils.nip_io.parse_nip", flaky)
        monkeypatch.setattr(nip_io.time, "sleep", lambda *_: None)
        result = nip_io.parse_nip_with_retry("ignored", attempts=3, delay=0.01)
        assert result == {42: 100}
        assert calls["n"] == 2

    def test_raises_after_attempts_exhausted(self, tmp_path, monkeypatch):
        from src.utils import nip_io

        def always_bad(path):
            raise UnicodeDecodeError("utf-16-le", b"", 0, 1, "truncated data")

        monkeypatch.setattr("src.utils.nip_io.parse_nip", always_bad)
        monkeypatch.setattr(nip_io.time, "sleep", lambda *_: None)
        with pytest.raises(UnicodeDecodeError):
            nip_io.parse_nip_with_retry("ignored", attempts=2, delay=0.01)
