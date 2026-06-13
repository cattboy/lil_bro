"""Tests for the DLSS-only NVIDIA fix path and the Dashboard NVIDIA cards.

Covers:
- fix_nvidia_dlss_preset writes ONLY the two DLSS SettingIDs, raises on an
  unmapped GPU generation, and raises when NPI is absent.
- The @register_fix("nvidia_dlss_preset") handler is registered and records a
  revertible manifest entry.
- revert_fix routes "nvidia_dlss_preset" to the whole-profile .nip restore.
- Dashboard.set_nvidia_data show/hide gating (NPI absent, consumer GeForce,
  workstation card, no NVIDIA).
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from src.utils.errors import SetterError
from src.utils.nvidia_npi import SETTING_IDS, TARGET_VALUES

_SPECS_5090 = {"NVIDIA": [{"GPU": "NVIDIA GeForce RTX 5090"}]}


class TestFixNvidiaDlssPreset:
    @patch("src.agent_tools.nvidia_profile_setter.apply_nvidia_profile", return_value=(True, "ok"))
    @patch("src.agent_tools.nvidia_profile_setter.build_optimized_nip", return_value="mod.nip")
    @patch("src.agent_tools.nvidia_profile_setter.export_current_profile", return_value=("src.nip", {}))
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="b.nip")
    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value="npi.exe")
    def test_writes_only_dlss_settings(self, _npi, _backup, _export, mock_build, _apply, tmp_path):
        from src.agent_tools.nvidia_profile_setter import fix_nvidia_dlss_preset
        with patch("src.agent_tools.nvidia_profile_setter.get_temp_dir", return_value=tmp_path), \
             patch("src.agent_tools.nvidia_profile_setter.os.unlink"):
            assert fix_nvidia_dlss_preset(_SPECS_5090) is True

        target = mock_build.call_args[0][1]
        # Exactly the two DLSS SettingIDs are written -- nothing else in the profile.
        assert set(target.keys()) == {
            SETTING_IDS["dlss_preset_profile"],
            SETTING_IDS["dlss_preset_letter"],
        }
        assert target[SETTING_IDS["dlss_preset_profile"]] == TARGET_VALUES["dlss_preset_profile"]
        # RTX 5090 is FP8 + default priority "quality" -> Preset M (0x0D / 13).
        assert target[SETTING_IDS["dlss_preset_letter"]] == 13

    @patch("src.agent_tools.nvidia_profile_setter.apply_nvidia_profile", return_value=(True, "ok"))
    @patch("src.agent_tools.nvidia_profile_setter.build_optimized_nip", return_value="mod.nip")
    @patch("src.agent_tools.nvidia_profile_setter.export_current_profile", return_value=("src.nip", {}))
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="b.nip")
    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value="npi.exe")
    def test_writes_k_for_no_fp8(self, _npi, _backup, _export, mock_build, _apply, tmp_path):
        from src.agent_tools.nvidia_profile_setter import fix_nvidia_dlss_preset
        specs = {"NVIDIA": [{"GPU": "NVIDIA GeForce RTX 3080"}]}
        with patch("src.agent_tools.nvidia_profile_setter.get_temp_dir", return_value=tmp_path), \
             patch("src.agent_tools.nvidia_profile_setter.os.unlink"):
            assert fix_nvidia_dlss_preset(specs) is True
        target = mock_build.call_args[0][1]
        # RTX 30-series (no FP8) -> Preset K (11) regardless of priority.
        assert target[SETTING_IDS["dlss_preset_letter"]] == 11

    @patch("src.agent_tools.nvidia_profile_setter.apply_nvidia_profile", return_value=(True, "ok"))
    @patch("src.agent_tools.nvidia_profile_setter.build_optimized_nip", return_value="mod.nip")
    @patch("src.agent_tools.nvidia_profile_setter.export_current_profile", return_value=("src.nip", {}))
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="b.nip")
    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value="npi.exe")
    def test_full_profile_excludes_dlss(self, _npi, _backup, _export, mock_build, _apply, tmp_path):
        """De-bundle: the FULL profile fix must NOT write the DLSS SettingIDs --
        DLSS is owned solely by fix_nvidia_dlss_preset. The other settings (e.g.
        power management) are still applied."""
        from src.agent_tools.nvidia_profile_setter import fix_nvidia_profile
        with patch("src.agent_tools.nvidia_profile_setter.get_temp_dir", return_value=tmp_path), \
             patch("src.agent_tools.nvidia_profile_setter.os.unlink"):
            assert fix_nvidia_profile(_SPECS_5090) is True
        target = mock_build.call_args[0][1]
        assert SETTING_IDS["dlss_preset_profile"] not in target
        assert SETTING_IDS["dlss_preset_letter"] not in target
        # Power management is always written by the profile fix.
        assert SETTING_IDS["power_mgmt"] in target  # M

    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value="npi.exe")
    def test_raises_on_unmapped_generation(self, _npi):
        from src.agent_tools.nvidia_profile_setter import fix_nvidia_dlss_preset
        # GTX 1080 has no RTX generation -> no DLSS_PRESETS mapping.
        with pytest.raises(SetterError):
            fix_nvidia_dlss_preset({"NVIDIA": [{"GPU": "NVIDIA GeForce GTX 1080"}]})

    @patch("src.agent_tools.nvidia_profile_setter.find_npi_exe", return_value=None)
    def test_raises_when_npi_missing(self, _npi):
        from src.agent_tools.nvidia_profile_setter import fix_nvidia_dlss_preset
        with pytest.raises(FileNotFoundError):
            fix_nvidia_dlss_preset(_SPECS_5090)


class TestDispatchNvidiaDlssPreset:
    def test_registered(self):
        from src.pipeline.fix_dispatch import FIX_REGISTRY
        assert "nvidia_dlss_preset" in FIX_REGISTRY

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.nvidia_profile_setter.fix_nvidia_dlss_preset", return_value=True)
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="b.nip")
    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    def test_execute_records_revertible(self, _npi, _backup, _fix, mock_append):
        from src.pipeline.fix_dispatch import execute_fix
        assert execute_fix("nvidia_dlss_preset", _SPECS_5090) is True
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][0]
        assert entry["fix"] == "nvidia_dlss_preset"
        assert entry["revertible"] is True
        assert entry["before_backup"] == "b.nip"

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.nvidia_profile_setter.fix_nvidia_dlss_preset", side_effect=Exception("boom"))
    @patch("src.agent_tools.nvidia_profile_setter.backup_nvidia_profile", return_value="b.nip")
    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    def test_execute_returns_false_on_failure(self, _npi, _backup, _fix, _append):
        from src.pipeline.fix_dispatch import execute_fix
        assert execute_fix("nvidia_dlss_preset", _SPECS_5090) is False


class TestRevertNvidiaDlssPreset:
    def test_revert_routes_to_whole_profile_restore(self):
        from src.utils import revert
        entry = {"fix": "nvidia_dlss_preset", "before_backup": "b.nip"}
        with patch.object(revert, "_revert_nvidia_profile", return_value=(True, "")) as mock_rev:
            ok, msg = revert.revert_fix(entry)
        assert ok is True
        mock_rev.assert_called_once_with(entry)


class TestDashboardSetNvidiaData:
    def _make_dashboard(self, qtbot):
        from src.gui.widgets.dashboard import Dashboard
        dash = Dashboard()
        qtbot.addWidget(dash)
        return dash

    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    def test_consumer_geforce_shows_both_cards(self, _npi, qtbot):
        dash = self._make_dashboard(qtbot)
        dash.set_nvidia_data([{"GPU": "NVIDIA GeForce RTX 5090"}])
        assert not dash._nvidia_full_card.isHidden()
        assert not dash._nvidia_dlss_card.isHidden()

    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    def test_workstation_card_hides_dlss(self, _npi, qtbot):
        # "RTX 2000 Ada Generation" lacks "GeForce" -> DLSS card must hide so we
        # never assert a regex-misread preset; the full card still applies.
        dash = self._make_dashboard(qtbot)
        dash.set_nvidia_data([{"GPU": "NVIDIA RTX 2000 Ada Generation"}])
        assert not dash._nvidia_full_card.isHidden()
        assert dash._nvidia_dlss_card.isHidden()

    @patch("src.utils.nvidia_npi.find_npi_exe", return_value=None)
    def test_npi_absent_hides_both(self, _npi, qtbot):
        dash = self._make_dashboard(qtbot)
        dash.set_nvidia_data([{"GPU": "NVIDIA GeForce RTX 5090"}])
        assert dash._nvidia_full_card.isHidden()
        assert dash._nvidia_dlss_card.isHidden()

    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    def test_no_nvidia_hides_both(self, _npi, qtbot):
        dash = self._make_dashboard(qtbot)
        dash.set_nvidia_data({"error": "nvidia-smi not found"})
        assert dash._nvidia_full_card.isHidden()
        assert dash._nvidia_dlss_card.isHidden()

    @patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe")
    def test_seed_dlss_priority_monitor_aware(self, _npi, qtbot, monkeypatch):
        import PySide6.QtCore as qtc

        class _FakeQS:
            def __init__(self, *a):
                pass

            def value(self, *a, **k):
                return None  # no stored manual choice

            def setValue(self, *a, **k):
                pass

        monkeypatch.setattr(qtc, "QSettings", _FakeQS)
        from src.config import config
        monkeypatch.setattr(config.nvidia.dlss, "priority", "fps")
        dash = self._make_dashboard(qtbot)
        dash.seed_dlss_priority(
            {"DisplayCapabilities": [{"max_refresh_hz": 60, "at_resolution": "1920x1080"}]}
        )
        # No manual QSettings; 60Hz monitor-aware -> quality (overrides config "fps").
        assert config.nvidia.dlss.priority == "quality"
