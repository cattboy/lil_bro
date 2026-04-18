"""Tests for revert routing: menu choice 4 and --revert CLI flag."""

from unittest.mock import patch, MagicMock


class TestMenuRevertRouting:
    @patch("src.pipeline.phase_revert.run_revert_phase")
    @patch("builtins.input", return_value="4")
    def test_menu_choice_4_calls_revert_phase(self, mock_input, mock_revert):
        """Menu choice '4' routes to run_revert_phase()."""
        from src.pipeline.menu import menu_loop

        # After revert, next input will be '3' (exit) to break the loop
        mock_input.side_effect = ["4", "3"]
        mock_lhm = MagicMock()

        with patch("src.pipeline.menu.get_llm", return_value=None):
            try:
                menu_loop(mock_lhm)
            except SystemExit:
                pass

        mock_revert.assert_called_once()


class TestCliRevertRouting:
    @patch("src.pipeline.phase_revert.run_revert_phase")
    @patch("src.main._parse_args")
    def test_revert_flag_routes_to_revert_phase(self, mock_args, mock_revert):
        """--revert flag bypasses menu, routes directly to run_revert_phase."""
        from src.main import main

        args = MagicMock()
        args.revert = True
        args.debug = False
        mock_args.return_value = args

        with patch("src.utils.integrity.verify_integrity"), \
             patch("src.main.print_banner"), \
             patch("src.main.check_admin"), \
             patch("src.main.action_logger"), \
             patch("src.main.resize_console_window"), \
             patch("src.main.save_default_config"), \
             patch("src.main.post_run_cleanup"):
            try:
                main()
            except SystemExit:
                pass

        mock_revert.assert_called_once()
