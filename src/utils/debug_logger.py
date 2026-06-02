"""
Persistent debug logger → ./lil_bro_debug.log (CWD root, survives cleanup).

Disabled by default — no file is created and no overhead is incurred unless
``--debug`` is passed on the command line.

Usage:
    # In main.py, before the pipeline starts:
    from src.utils.debug_logger import enable_debug_logging
    enable_debug_logging()

    # Everywhere else:
    from src.utils.debug_logger import get_debug_logger
    log = get_debug_logger()
    log.info("Phase 2 started")
    log.warning("Collector %s failed: %s", name, e)
    log.error("Unexpected exception: %s", e, exc_info=True)
"""

import logging
from logging.handlers import RotatingFileHandler

from .paths import get_debug_log_path

_debug_enabled: bool = False
_debug_level: int = logging.DEBUG
_logger: logging.Logger | None = None


def enable_debug_logging(level: int = logging.DEBUG) -> None:
    """Activate debug logging. Must be called before get_debug_logger() is first used.

    Defaults to DEBUG; pass logging.INFO for always-on GUI mode.
    """
    global _debug_enabled, _debug_level, _logger
    _debug_enabled = True
    _debug_level = level
    _logger = None  # Force re-init: module-level log = get_debug_logger() calls that
                    # fired before this (e.g. lhm_sidecar at import time) cached a
                    # NullHandler.  Resetting here lets get_debug_logger() attach the
                    # handler to the same logger instance, which all existing
                    # references will immediately see (logging resolves by name).


def get_debug_logger() -> logging.Logger:
    """Return the shared lil_bro debug logger, initializing it on first call.

    When debug logging is disabled (default), returns a logger wired to
    NullHandler at level CRITICAL+1 — all calls are no-ops and no file is created.
    When enabled via enable_debug_logging(), writes to lil_bro_debug.log at DEBUG level.
    """
    global _logger
    if _logger is not None:
        return _logger

    logger = logging.getLogger("lil_bro")

    if not _debug_enabled:
        logger.setLevel(logging.CRITICAL + 1)
        logger.addHandler(logging.NullHandler())
        _logger = logger
        return _logger

    # Debug mode: write to persistent log file at CWD root
    logger.setLevel(_debug_level)
    log_path = get_debug_log_path()
    handler = RotatingFileHandler(log_path, maxBytes=50 * 1024 * 1024, backupCount=1, encoding="utf-8")
    handler.setLevel(_debug_level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)

    # Write a session separator so multi-run log files stay readable
    from src._version import __version__
    logger.info("=" * 60)
    logger.info("SESSION START  |  lil_bro v%s", __version__)
    logger.info("=" * 60)

    _logger = logger
    return _logger