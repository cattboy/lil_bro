"""Tests for ActionLogger session separator methods."""

from unittest.mock import patch

from src.utils.action_logger import ActionLogger


def _make_logger(tmp_path):
    return ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"))


# ---------------------------------------------------------------------------
# log_session_start
# ---------------------------------------------------------------------------

def test_session_start_new_file_writes_separator(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_start()

    content = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8")
    assert content.startswith("=" * 80)
    assert "SESSION START" in content


def test_session_start_new_file_no_leading_blank_line(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_start()

    content = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8")
    assert not content.startswith("\n"), "New log file must not start with a blank line"


def test_session_start_existing_file_prepends_blank_line(tmp_path):
    log_path = tmp_path / "lil_bro_actions.log"
    log_path.write_text("[2026-01-01 00:00:00] [PowerCfg] something\n", encoding="utf-8")

    logger = ActionLogger(log_path=str(log_path))
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_start()

    content = log_path.read_text(encoding="utf-8")
    # The separator block should be preceded by a blank line
    assert "\n\n" in content, "Expected a blank line before the separator on existing file"
    assert "SESSION START" in content


def test_session_start_includes_version(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_start()

    content = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8")
    from src._version import __version__
    assert __version__ in content


def test_session_start_separator_width(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_start()

    lines = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "=" * 80
    assert lines[2] == "=" * 80


# ---------------------------------------------------------------------------
# log_session_end
# ---------------------------------------------------------------------------

def test_session_end_writes_marker(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_end()

    content = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8")
    assert "SESSION END" in content


def test_session_end_single_line(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_end()

    lines = [l for l in (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8").splitlines() if l]
    assert len(lines) == 1
    assert "SESSION END" in lines[0]


# ---------------------------------------------------------------------------
# round-trip: start → actions → end
# ---------------------------------------------------------------------------

def test_full_session_structure(tmp_path):
    logger = _make_logger(tmp_path)
    with patch("src.utils.formatting.print_dim"):
        logger.log_session_start()
        logger.log_action("PowerCfg", "Switched plan", "guid-abc")
        logger.log_session_end()

    content = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8")
    lines = content.splitlines()
    assert lines[0] == "=" * 80
    assert "SESSION START" in lines[1]
    assert lines[2] == "=" * 80
    assert "PowerCfg" in lines[3]
    assert "SESSION END" in lines[4]
