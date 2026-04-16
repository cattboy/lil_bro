"""Tests for src.pipeline.fix_dispatch -- dispatch registry + handlers."""
from unittest.mock import patch, MagicMock
from src.pipeline.fix_dispatch import FIX_REGISTRY, execute_fix


class TestFixRegistry:
    def test_all_expected_checks_registered(self):
        """All auto-fixable checks must be in the registry."""
        expected = {"display", "power_plan", "temp_folders", "game_mode", "nvidia_profile"}
        assert set(FIX_REGISTRY.keys()) == expected

    def test_all_handlers_are_callable(self):
        for name, handler in FIX_REGISTRY.items():
            assert callable(handler), f"{name} handler is not callable"

    def test_unknown_check_returns_false(self):
        assert execute_fix("nonexistent_check", {}) is False


class TestFixGameMode:
    @patch("src.agent_tools.game_mode.set_game_mode")
    def test_game_mode_success(self, mock_set):
        assert execute_fix("game_mode", {}) is True
        mock_set.assert_called_once_with(enabled=True)

    @patch("src.agent_tools.game_mode.set_game_mode", side_effect=Exception("denied"))
    def test_game_mode_failure(self, mock_set):
        assert execute_fix("game_mode", {}) is False

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.game_mode.set_game_mode")
    def test_game_mode_manifest_entry_captured(self, mock_set, mock_append):
        """Manifest entry written with before-state from specs."""
        specs = {"GameMode": {"enabled": False}}
        assert execute_fix("game_mode", specs) is True
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][0]
        assert entry["fix"] == "game_mode"
        assert entry["revertible"] is True
        assert entry["before"]["AutoGameModeEnabled"] == 0
        assert entry["after"]["AutoGameModeEnabled"] == 1


class TestFixTempFolders:
    @patch("src.agent_tools.temp_audit.clean_temp_folders")
    def test_temp_cleanup_success(self, mock_clean):
        specs = {"TempFolders": {"details": {"/tmp": 1000}}}
        assert execute_fix("temp_folders", specs) is True
        mock_clean.assert_called_once_with({"/tmp": 1000})

    @patch("src.agent_tools.temp_audit.clean_temp_folders")
    def test_temp_cleanup_empty_specs(self, mock_clean):
        assert execute_fix("temp_folders", {}) is True
        mock_clean.assert_called_once_with({})


class TestFixDisplay:
    @patch("src.agent_tools.display_setter.apply_display_mode")
    @patch("src.agent_tools.display_setter.find_best_mode")
    @patch("src.collectors.sub.monitor_dumper.get_all_displays", return_value=["\\\\.\\DISPLAY1"])
    def test_display_success(self, mock_displays, mock_find, mock_apply):
        mock_mode = MagicMock()
        mock_mode.dmDisplayFrequency = 144
        mock_mode.dmPelsWidth = 1920
        mock_mode.dmPelsHeight = 1080
        mock_find.return_value = mock_mode
        mock_apply.side_effect = [(True, "Validated"), (True, "Applied")]
        assert execute_fix("display", {}) is True

    @patch("src.agent_tools.display_setter.find_best_mode", return_value=None)
    @patch("src.collectors.sub.monitor_dumper.get_all_displays", return_value=[])
    def test_display_no_mode_found(self, mock_displays, mock_find):
        assert execute_fix("display", {}) is False

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.display_setter.apply_display_mode")
    @patch("src.agent_tools.display_setter.find_best_mode")
    @patch("src.agent_tools.display_setter.get_current_display_mode")
    @patch("src.collectors.sub.monitor_dumper.get_all_displays", return_value=["\\\\.\\DISPLAY1"])
    def test_display_manifest_entry_captured(self, mock_displays, mock_current, mock_find, mock_apply, mock_append):
        """Manifest entry written with before/after display state."""
        before = MagicMock()
        before.dmPelsWidth = 1920
        before.dmPelsHeight = 1080
        before.dmDisplayFrequency = 60
        mock_current.return_value = before

        after = MagicMock()
        after.dmPelsWidth = 1920
        after.dmPelsHeight = 1080
        after.dmDisplayFrequency = 144
        mock_find.return_value = after
        mock_apply.side_effect = [(True, "Validated"), (True, "Applied")]

        assert execute_fix("display", {}) is True
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][0]
        assert entry["fix"] == "display"
        assert entry["revertible"] is True
        assert entry["before"]["hz"] == 60
        assert entry["after"]["hz"] == 144


class TestFixPowerPlan:
    @patch("src.agent_tools.power_plan.set_active_plan")
    @patch("src.agent_tools.power_plan.list_available_plans")
    def test_power_plan_success_via_perf_guid(self, mock_list, mock_set):
        """Handler picks first plan matching a known PERF_GUID."""
        from src.agent_tools.power_plan import _PERF_GUIDS
        guid = next(iter(_PERF_GUIDS))
        mock_list.return_value = [(guid, "High performance")]
        assert execute_fix("power_plan", {}) is True
        mock_set.assert_called_once_with(guid)

    @patch("src.agent_tools.power_plan.set_active_plan")
    @patch("src.agent_tools.power_plan.list_available_plans")
    def test_power_plan_success_via_name_match(self, mock_list, mock_set):
        """Handler falls back to name match when no PERF_GUID matches."""
        mock_list.return_value = [("aaaa-bbbb", "High Performance Plan")]
        assert execute_fix("power_plan", {}) is True
        mock_set.assert_called_once_with("aaaa-bbbb")

    @patch("src.agent_tools.power_plan.set_active_plan")
    @patch("src.agent_tools.power_plan.create_high_performance_plan", return_value=("cccc-dddd", "Custom HP"))
    @patch("src.agent_tools.power_plan.list_available_plans", return_value=[])
    def test_power_plan_creates_new_when_none_found(self, mock_list, mock_create, mock_set):
        """Handler creates a new plan when no matching plan exists."""
        assert execute_fix("power_plan", {}) is True
        mock_create.assert_called_once()
        mock_set.assert_called_once_with("cccc-dddd")

    @patch("src.agent_tools.power_plan.list_available_plans", side_effect=Exception("powercfg failed"))
    def test_power_plan_failure(self, mock_list):
        assert execute_fix("power_plan", {}) is False

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.power_plan.set_active_plan")
    @patch("src.agent_tools.power_plan.list_available_plans")
    def test_power_plan_manifest_entry_captured(self, mock_list, mock_set, mock_append):
        """Manifest entry written with correct before-state from specs."""
        from src.agent_tools.power_plan import _PERF_GUIDS
        guid = next(iter(_PERF_GUIDS))
        mock_list.return_value = [(guid, "High performance")]
        specs = {"PowerPlan": {"guid": "aaa-bbb", "name": "Balanced"}}
        assert execute_fix("power_plan", specs) is True
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][0]
        assert entry["fix"] == "power_plan"
        assert entry["revertible"] is True
        assert entry["before"]["guid"] == "aaa-bbb"
        assert entry["before"]["name"] == "Balanced"

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.power_plan.set_active_plan")
    @patch("src.agent_tools.power_plan.list_available_plans")
    def test_power_plan_missing_before_state_marks_not_revertible(self, mock_list, mock_set, mock_append):
        """Empty specs → manifest entry revertible=False, fix still proceeds."""
        from src.agent_tools.power_plan import _PERF_GUIDS
        guid = next(iter(_PERF_GUIDS))
        mock_list.return_value = [(guid, "High performance")]
        assert execute_fix("power_plan", {}) is True
        mock_append.assert_called_once()
        entry = mock_append.call_args[0][0]
        assert entry["revertible"] is False

    @patch("src.utils.revert.append_fix_to_manifest")
    @patch("src.agent_tools.power_plan.list_available_plans", side_effect=Exception("powercfg failed"))
    def test_power_plan_failure_no_manifest_written(self, mock_list, mock_append):
        """When set_active_plan raises, no manifest entry is written."""
        assert execute_fix("power_plan", {}) is False
        mock_append.assert_not_called()
