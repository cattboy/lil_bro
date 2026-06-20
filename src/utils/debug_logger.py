"""
Persistent debug logger → ./lil_bro_debug.log (CWD root, survives cleanup).

Error-only by default: a clean run creates no file. The handler uses
``delay=True`` and the logger sits at ERROR level, so the file is opened only
when a crash logs an ERROR/CRITICAL record (the traceback). Passing ``--debug``
raises the level to DEBUG, emitting the SESSION banner and the full verbose log
from startup. When logging was never enabled at all, a NullHandler makes every
call a no-op.

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

    Pass logging.ERROR for the normal GUI fallback (no file on a clean run; the
    delay=True handler opens lil_bro_debug.log only when a crash logs an ERROR).
    Pass logging.DEBUG (--debug) for the full verbose log with the SESSION banner.
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
    When enabled via enable_debug_logging():
      - at ERROR level (normal GUI mode), the delay=True handler opens
        lil_bro_debug.log only on the first ERROR/CRITICAL record, so a clean
        run leaves no file but a crash still writes its traceback.
      - at DEBUG level (--debug), the SESSION banner emits immediately, so the
        full verbose log appears at startup.
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

    # Enabled: write to persistent log file at CWD root. delay=True defers the
    # file open until the first record passes the level filter, so at ERROR
    # level a crash-free run never creates the file.
    logger.setLevel(_debug_level)
    log_path = get_debug_log_path()
    handler = RotatingFileHandler(
        log_path, maxBytes=50 * 1024 * 1024, backupCount=1, encoding="utf-8", delay=True
    )
    handler.setLevel(_debug_level)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)

    # Write a session separator so multi-run log files stay readable. These are
    # INFO records: under --debug (DEBUG level) they fire and open the file now;
    # in error-only mode (ERROR level) they are filtered, so no file is created
    # until a real ERROR record arrives.
    from src._version import __version__
    logger.info("=" * 60)
    logger.info("SESSION START  |  lil_bro v%s", __version__)
    logger.info("=" * 60)

    _logger = logger
    return _logger


def log_crash(log: logging.Logger, where: str, exc_info) -> None:
    """Log an uncaught-exception record stamped with the app version.

    Used by every crash sink (sys.excepthook, threading.excepthook,
    PipelineWorker.run) so error-only crash logs self-identify the build even
    though the INFO SESSION banner is filtered at ERROR level. ``exc_info`` may
    be a ``(type, value, tb)`` tuple or ``True`` (current exception).
    """
    from src._version import __version__
    log.error("lil_bro v%s — %s", __version__, where, exc_info=exc_info)
