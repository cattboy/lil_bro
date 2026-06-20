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
    from src._version import __version__
    first_line = content.splitlines()[0]
    # Top line is a version banner: == padding around " lil_bro vX.Y.Z.W ".
    assert first_line.startswith("=") and first_line.endswith("=")
    assert len(first_line) == 80
    assert f"lil_bro v{__version__}" in first_line
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

    from src._version import __version__
    lines = (tmp_path / "lil_bro_actions.log").read_text(encoding="utf-8").splitlines()
    # Line 0 is the version banner (80 wide, version embedded); line 2 is plain.
    assert len(lines[0]) == 80
    assert lines[0].startswith("=") and lines[0].endswith("=")
    assert f"lil_bro v{__version__}" in lines[0]
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
    from src._version import __version__
    lines = content.splitlines()
    assert len(lines[0]) == 80 and f"lil_bro v{__version__}" in lines[0]  # version banner
    assert "SESSION START" in lines[1]
    assert lines[2] == "=" * 80
    assert "PowerCfg" in lines[3]
    assert "SESSION END" in lines[4]


# ---------------------------------------------------------------------------
# _rotate_if_needed
# ---------------------------------------------------------------------------

def test_rotate_not_triggered_below_cap(tmp_path):
    from unittest.mock import patch
    logger = _make_logger(tmp_path)
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("x" * 100, encoding="utf-8")
    logger.log_action("Test", "action")
    content = log_file.read_text(encoding="utf-8")
    assert "LOG ROTATED" not in content
    assert "Test" in content


def test_rotate_fires_at_cap(tmp_path):
    from unittest.mock import patch
    from src.utils.action_logger import ActionLogger

    echo_calls = []
    logger = ActionLogger(
        log_path=str(tmp_path / "lil_bro_actions.log"),
        echo_fn=echo_calls.append,
    )
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("existing content", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "action after cap")
    content = log_file.read_text(encoding="utf-8")
    assert "LOG STOPPED" in content
    assert "action after cap" not in content  # write refused after hard stop
    assert any("100 MB cap" in msg for msg in echo_calls), "Expected cap warning via echo_fn"


def test_rotate_marker_is_first_line(tmp_path):
    from unittest.mock import patch
    logger = _make_logger(tmp_path)
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("old data", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "action")
    lines = log_file.read_text(encoding="utf-8").splitlines()
    assert "LOG STOPPED" in lines[0]


def test_rotate_no_echo_when_no_echo_fn(tmp_path):
    """Rotation with no _echo_fn set must not raise."""
    from unittest.mock import patch
    logger = _make_logger(tmp_path)
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "safe without echo")
    assert "LOG STOPPED" in log_file.read_text(encoding="utf-8")


def test_rotate_hard_stop_refuses_subsequent_writes(tmp_path):
    from unittest.mock import patch
    from src.utils.action_logger import ActionLogger

    logger = ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"))
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("First", "triggers cap")
        logger.log_action("Second", "should be refused")
    content = log_file.read_text(encoding="utf-8")
    assert "First" not in content
    assert "Second" not in content
    assert "LOG STOPPED" in content


def test_rotate_new_instance_resumes_writes(tmp_path):
    from src.utils.action_logger import ActionLogger

    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text(
        "[LOG STOPPED — 100 MB cap reached. Remove this file to resume logging.]\n",
        encoding="utf-8",
    )
    logger = ActionLogger(log_path=str(log_file))
    logger.log_action("Fresh", "run after cap")
    content = log_file.read_text(encoding="utf-8")
    assert "Fresh" in content


# ---------------------------------------------------------------------------
# _rotate_if_needed — GUI cap notification (T-016)
# ---------------------------------------------------------------------------

def test_cap_fires_gui_notify(tmp_path):
    """The injected gui_notify_fn fires once when the cap is hit."""
    from unittest.mock import Mock, patch
    from src.utils.action_logger import ActionLogger

    notify = Mock()
    logger = ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"), gui_notify_fn=notify)
    (tmp_path / "lil_bro_actions.log").write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "triggers cap")
    notify.assert_called_once()


def test_cap_notify_fires_once(tmp_path):
    """The _cap_reached guard means notify fires at most once across writes."""
    from unittest.mock import Mock, patch
    from src.utils.action_logger import ActionLogger

    notify = Mock()
    logger = ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"), gui_notify_fn=notify)
    (tmp_path / "lil_bro_actions.log").write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("First", "triggers cap")
        logger.log_action("Second", "refused")
    notify.assert_called_once()


def test_cap_fires_both_echo_and_gui(tmp_path):
    """When both callbacks are set, the cap branch fires both (additive)."""
    from unittest.mock import Mock, patch
    from src.utils.action_logger import ActionLogger

    echo, notify = Mock(), Mock()
    logger = ActionLogger(
        log_path=str(tmp_path / "lil_bro_actions.log"), echo_fn=echo, gui_notify_fn=notify
    )
    (tmp_path / "lil_bro_actions.log").write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "triggers cap")
    notify.assert_called_once()
    assert any("100 MB cap" in str(c) for c in echo.call_args_list), "echo_fn should also warn"


def test_cap_no_gui_notify_safe(tmp_path):
    """Default gui_notify_fn=None must not raise and still hard-stops logging."""
    from unittest.mock import patch
    from src.utils.action_logger import ActionLogger

    logger = ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"))
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "safe without notify")
    assert "LOG STOPPED" in log_file.read_text(encoding="utf-8")


def test_cap_notify_failure_is_swallowed(tmp_path):
    """A raising gui_notify_fn must never corrupt the logging path."""
    from unittest.mock import Mock, patch
    from src.utils.action_logger import ActionLogger

    notify = Mock(side_effect=RuntimeError("GUI gone"))
    logger = ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"), gui_notify_fn=notify)
    log_file = tmp_path / "lil_bro_actions.log"
    log_file.write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024):
        logger.log_action("Test", "notify raises")  # must not propagate
    notify.assert_called_once()
    assert "LOG STOPPED" in log_file.read_text(encoding="utf-8")


def test_cap_logs_to_debug_logger(tmp_path):
    """The cap event is recorded in the separate persistent debug log."""
    from unittest.mock import Mock, patch
    from src.utils.action_logger import ActionLogger

    dbg = Mock()
    logger = ActionLogger(log_path=str(tmp_path / "lil_bro_actions.log"))
    (tmp_path / "lil_bro_actions.log").write_text("existing", encoding="utf-8")
    with patch("src.utils.action_logger.os.path.getsize", return_value=100 * 1024 * 1024), \
         patch("src.utils.debug_logger.get_debug_logger", return_value=dbg):
        logger.log_action("Test", "triggers cap")
    dbg.error.assert_called_once()
    assert "100 MB cap" in str(dbg.error.call_args)


# ---------------------------------------------------------------------------
# session() — lazy session context manager
# ---------------------------------------------------------------------------

def test_session_no_writes_emits_nothing(tmp_path):
    """A no-op pass inside session() writes no banner / START / END."""
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))
    with logger.session():
        pass
    content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert content == ""


def test_session_lazy_banner_before_first_action(tmp_path):
    """Banner + SESSION START flush before the first entry; SESSION END after."""
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))
    with logger.session():
        logger.log_action("PowerCfg", "Switched plan", "guid-abc")
    from src._version import __version__
    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines[0]) == 80 and f"lil_bro v{__version__}" in lines[0]  # version banner
    assert "SESSION START" in lines[1]
    assert lines[2] == "=" * 80
    assert "PowerCfg" in lines[3]
    assert "SESSION END" in lines[4]


def test_session_no_end_when_no_start(tmp_path):
    """No START flushed -> no SESSION END line either (no empty block)."""
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))
    with logger.session():
        pass
    content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert "SESSION END" not in content


def test_session_emits_end_on_exception_after_write(tmp_path):
    """An exception after a logged action still closes the session (finally)."""
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))
    try:
        with logger.session():
            logger.log_action("Revert", "Game Mode restored")
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    content = log_path.read_text(encoding="utf-8")
    assert "SESSION START" in content
    assert "Revert" in content
    assert "SESSION END" in content


def test_session_no_block_on_exception_before_write(tmp_path):
    """An exception before any write leaves nothing (no empty session block)."""
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))
    try:
        with logger.session():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    content = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
    assert content == ""


def test_session_flush_triggered_by_fix_dispatch(tmp_path):
    """log_fix_dispatch / log_fix_result (which call log_action) flush the banner."""
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))
    with logger.session():
        logger.log_fix_dispatch("power_plan")
        logger.log_fix_result("power_plan", True)
    content = log_path.read_text(encoding="utf-8")
    assert "SESSION START" in content
    assert "Dispatching fix: power_plan" in content
    assert "Fix complete: power_plan" in content
    assert "SESSION END" in content


def test_session_thread_isolation(tmp_path):
    """A session armed on one thread must NOT make another thread's log_action
    flush a banner. Regression guard for the thread-local session state."""
    import threading

    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path))

    armed = threading.Event()
    release = threading.Event()

    def hold_session():
        with logger.session():
            armed.set()
            release.wait(2.0)  # keep the session armed on THIS thread only

    t = threading.Thread(target=hold_session)
    t.start()
    armed.wait(2.0)
    # Log from the main thread while the worker's session is armed.
    logger.log_action("Other", "main-thread entry")
    release.set()
    t.join(2.0)

    content = log_path.read_text(encoding="utf-8")
    first_line = content.splitlines()[0]
    # The main-thread entry must NOT have a banner in front of it: the worker's
    # armed session is thread-local and must not bleed across threads.
    assert "SESSION START" not in first_line
    assert "lil_bro v" not in first_line
    assert "main-thread entry" in content


def test_session_echo_parity(tmp_path):
    """With an echo fn set, the banner header is echoed before the first entry."""
    echoed: list[str] = []
    log_path = tmp_path / "lil_bro_actions.log"
    logger = ActionLogger(log_path=str(log_path), echo_fn=echoed.append)
    with logger.session():
        logger.log_action("Revert", "Display restored")
    assert any("SESSION START" in e for e in echoed)
    start_idx = next(i for i, e in enumerate(echoed) if "SESSION START" in e)
    entry_idx = next(i for i, e in enumerate(echoed) if "Display restored" in e)
    assert start_idx < entry_idx
