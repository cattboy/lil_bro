"""Tests for src/utils/revert.py."""

from __future__ import annotations



import json

from unittest.mock import patch






from src.utils.revert import (

    append_fix_to_manifest,

    load_manifest,

    revert_fix,

    start_session_manifest,

    trigger_system_restore,

)





# ---------------------------------------------------------------------------

# start_session_manifest

# ---------------------------------------------------------------------------





import src.utils.revert as revert_mod

class TestStartSessionManifest:

    def setup_method(self):
        revert_mod._pending_manifest = None

    def teardown_method(self):
        revert_mod._pending_manifest = None

    def test_stages_manifest_in_memory(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            start_session_manifest(restore_point_created=True)
        assert not manifest_path.exists()
        pending = revert_mod._pending_manifest
        assert pending is not None
        assert "session_id" in pending
        assert "session_date" in pending
        assert pending["restore_point_created"] is True
        assert pending["fixes"] == []

    def test_does_not_write_file_to_disk(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            start_session_manifest()
        assert not manifest_path.exists()

    def test_second_call_replaces_pending_manifest(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            start_session_manifest(restore_point_created=True)
            start_session_manifest(restore_point_created=False)
        assert revert_mod._pending_manifest is not None
        assert revert_mod._pending_manifest["restore_point_created"] is False





# ---------------------------------------------------------------------------

# append_fix_to_manifest

# ---------------------------------------------------------------------------





class TestAppendFixToManifest:

    def setup_method(self):
        revert_mod._pending_manifest = None

    def teardown_method(self):
        revert_mod._pending_manifest = None

    def test_first_call_flushes_pending_to_disk(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        entry = {"fix": "power_plan", "revertible": True}
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            start_session_manifest(restore_point_created=True)
            assert not manifest_path.exists()
            append_fix_to_manifest(entry)
        assert manifest_path.exists()
        data = json.loads(manifest_path.read_text())
        assert len(data["fixes"]) == 1
        assert data["fixes"][0]["fix"] == "power_plan"
        assert revert_mod._pending_manifest is None

    def test_no_file_written_if_no_fixes_applied(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            start_session_manifest()
        assert not manifest_path.exists()

    def test_archives_previous_session_on_first_fix(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        manifest_path.write_text(json.dumps({"session_id": "old123", "fixes": []}))
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            start_session_manifest()
            append_fix_to_manifest({"fix": "game_mode"})
        assert (tmp_path / "session_old123.json").exists()

    def test_appends_entry_to_fixes(self, tmp_path):
        # Subsequent-call path: no pending manifest, file already on disk.
        manifest_path = tmp_path / "session_latest.json"
        manifest_path.write_text(json.dumps({"session_id": "x", "fixes": []}))
        entry = {"fix": "power_plan", "revertible": True}
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path):
            append_fix_to_manifest(entry)
        data = json.loads(manifest_path.read_text())
        assert len(data["fixes"]) == 1
        assert data["fixes"][0]["fix"] == "power_plan"

    def test_write_failure_calls_warning_no_raise(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        manifest_path.write_text(json.dumps({"session_id": "x", "fixes": []}))
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path), \
             patch("pathlib.Path.write_text", side_effect=OSError("disk full")), \
             patch("src.utils.revert.print_warning") as mock_warn:
            append_fix_to_manifest({"fix": "game_mode"})  # must not raise
        mock_warn.assert_called()

    def test_corrupt_manifest_graceful(self, tmp_path):
        manifest_path = tmp_path / "session_latest.json"
        manifest_path.write_text("NOT JSON {{{")
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path), \
             patch("src.utils.revert.print_warning"):
            append_fix_to_manifest({"fix": "game_mode"})  # must not raise

    def test_missing_manifest_warns(self, tmp_path):
        manifest_path = tmp_path / "missing.json"
        with patch("src.utils.revert.get_session_backup_path", return_value=manifest_path), \
             patch("src.utils.revert.print_warning") as mock_warn:
            append_fix_to_manifest({"fix": "game_mode"})
        mock_warn.assert_called()  # must not raise





# ---------------------------------------------------------------------------

# load_manifest

# ---------------------------------------------------------------------------





class TestLoadManifest:



    def test_returns_none_if_not_found(self, tmp_path):

        missing = tmp_path / "missing.json"

        with patch("src.utils.revert.get_session_backup_path", return_value=missing):

            assert load_manifest() is None



    def test_returns_none_on_json_error(self, tmp_path):

        bad = tmp_path / "bad.json"

        bad.write_text("NOT JSON")

        with patch("src.utils.revert.get_session_backup_path", return_value=bad):

            assert load_manifest() is None


    def test_json_error_logs_warning(self, tmp_path):
        bad = tmp_path / "corrupt.json"
        bad.write_text("NOT JSON")
        with patch("src.utils.revert.get_session_backup_path", return_value=bad), \
             patch("src.utils.revert.print_warning") as mock_warn:
            assert load_manifest() is None
        mock_warn.assert_called_once()





# ---------------------------------------------------------------------------

# revert_fix

# ---------------------------------------------------------------------------





class TestRevertFix:



    def test_power_plan_calls_set_active_plan(self):

        entry = {"fix": "power_plan", "before": {"guid": "abc-123", "name": "Balanced"}}

        with patch("src.agent_tools.power_plan.set_active_plan") as mock_set:

            ok, err = revert_fix(entry)

        assert ok is True

        assert err == ""

        mock_set.assert_called_once_with("abc-123")



    def test_game_mode_calls_winreg_set_value(self):

        entry = {"fix": "game_mode", "before": {"AutoGameModeEnabled": 0}}

        with patch("winreg.CreateKeyEx"), patch("winreg.SetValueEx") as mock_set:

            ok, err = revert_fix(entry)

        assert ok is True

        args = mock_set.call_args[0]

        assert args[1] == "AutoGameModeEnabled"

        assert args[4] == 0



    def test_nvidia_profile_calls_apply(self, tmp_path):

        nip = tmp_path / "backup.nip"

        nip.write_text("fake")

        entry = {"fix": "nvidia_profile", "before_backup": str(nip)}

        with patch("src.utils.nvidia_npi.find_npi_exe", return_value="npi.exe"), \
             patch("src.agent_tools.nvidia_profile_setter.apply_nvidia_profile", return_value=(True, "ok")) as mock_apply:

            ok, err = revert_fix(entry)

        assert ok is True

        mock_apply.assert_called_once_with("npi.exe", str(nip))



    def test_nvidia_profile_missing_nip_returns_false(self, tmp_path):

        entry = {"fix": "nvidia_profile", "before_backup": str(tmp_path / "missing.nip")}

        ok, err = revert_fix(entry)

        assert ok is False

        assert "not found" in err



    def test_display_calls_change_display_settings(self):

        entry = {

            "fix": "display",

            "before": {"device": "\\\\.\\DISPLAY1", "width": 2560, "height": 1440, "hz": 60},

        }

        with patch("ctypes.windll.user32.ChangeDisplaySettingsExW", return_value=0) as mock_cds:

            ok, err = revert_fix(entry)

        assert ok is True

        assert mock_cds.called



    def test_unknown_fix_key_returns_false(self):

        ok, err = revert_fix({"fix": "nonexistent_fix"})

        assert ok is False

        assert "No revert handler" in err





# ---------------------------------------------------------------------------

# trigger_system_restore

# ---------------------------------------------------------------------------





class TestTriggerSystemRestore:



    def test_launches_rstrui_returns_true(self):

        with patch("subprocess.Popen") as mock_popen:

            result = trigger_system_restore("2026-04-14")

        assert result is True

        mock_popen.assert_called_once_with(["rstrui.exe"])



    def test_subprocess_failure_returns_false(self):

        with patch("subprocess.Popen", side_effect=OSError("not found")), \
             patch("src.utils.revert.print_error") as mock_err:

            result = trigger_system_restore("2026-04-14")

        assert result is False

        mock_err.assert_called()
