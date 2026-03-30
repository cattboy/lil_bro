import logging

import pytest


def _reset_debug_logger():
    """Reset the debug_logger module state (singleton + flag) and stdlib logger between tests."""
    import src.utils.debug_logger as mod
    mod._logger = None
    mod._debug_enabled = False
    logger = logging.getLogger("lil_bro")
    for h in logger.handlers[:]:
        h.close()
        logger.removeHandler(h)


@pytest.fixture(autouse=True)
def isolate_logger(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _reset_debug_logger()
    yield
    _reset_debug_logger()


# --- Enabled (--debug) behaviour ---

def test_logger_writes_to_debug_log_path(tmp_path):
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger
    from src.utils.paths import get_debug_log_path

    enable_debug_logging()
    log = get_debug_logger()
    log.info("test message")

    for h in log.handlers:
        h.flush()

    log_file = get_debug_log_path()
    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "SESSION START" in content
    assert "test message" in content


def test_logger_is_singleton(tmp_path):
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger

    enable_debug_logging()
    a = get_debug_logger()
    b = get_debug_logger()
    assert a is b


def test_logger_no_duplicate_handlers(tmp_path):
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger

    enable_debug_logging()
    get_debug_logger()
    get_debug_logger()
    get_debug_logger()

    logger = logging.getLogger("lil_bro")
    assert len(logger.handlers) == 1


def test_logger_debug_level(tmp_path):
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger
    from src.utils.paths import get_debug_log_path

    enable_debug_logging()
    log = get_debug_logger()
    log.debug("a debug entry")

    for h in log.handlers:
        h.flush()

    content = get_debug_log_path().read_text(encoding="utf-8")
    assert "a debug entry" in content


def test_logger_warning_recorded(tmp_path):
    from src.utils.debug_logger import enable_debug_logging, get_debug_logger
    from src.utils.paths import get_debug_log_path

    enable_debug_logging()
    log = get_debug_logger()
    log.warning("something went wrong: %s", "oops")

    for h in log.handlers:
        h.flush()

    content = get_debug_log_path().read_text(encoding="utf-8")
    assert "WARNING" in content
    assert "something went wrong: oops" in content


# --- Disabled (default) behaviour ---

def test_disabled_creates_no_file(tmp_path):
    from src.utils.debug_logger import get_debug_logger
    from src.utils.paths import get_debug_log_path

    log = get_debug_logger()
    log.info("this should be dropped")
    log.warning("also dropped")

    assert not get_debug_log_path().exists()


def test_disabled_is_singleton(tmp_path):
    from src.utils.debug_logger import get_debug_logger

    a = get_debug_logger()
    b = get_debug_logger()
    assert a is b


def test_disabled_no_duplicate_handlers(tmp_path):
    from src.utils.debug_logger import get_debug_logger

    get_debug_logger()
    get_debug_logger()

    logger = logging.getLogger("lil_bro")
    # NullHandler only — never more than one
    assert len(logger.handlers) == 1
    assert isinstance(logger.handlers[0], logging.NullHandler)
