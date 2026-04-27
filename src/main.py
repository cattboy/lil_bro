"""
lil_bro -- Entry point.

Thin wrapper that handles:
  - multiprocessing freeze_support (PyInstaller)
  - File integrity verification (frozen builds)
  - Admin privilege check
  - Delegates to pipeline.menu for the main loop
"""

import argparse
import multiprocessing
import sys

from src.utils.action_logger import action_logger
from src.utils.formatting import print_info, print_warning, print_error, print_accent, print_dim, resize_console_window
from src.utils.errors import AdminRequiredError
from src.bootstrapper import check_admin
from src.pipeline.banner import print_banner
from src.pipeline.menu import menu_loop
from src.pipeline.startup_thermals import run_startup_thermal_scan
from src.config import save_default_config
from src.pipeline.post_run_cleanup import post_run_cleanup


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="lil_bro",
        description="Local AI gaming PC optimizer",
        add_help=True,
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging to lil_bro_debug.log (CWD root)",
    )
    parser.add_argument(
        "--revert",
        action="store_true",
        help="Revert the last lil_bro session without running the full pipeline.",
    )
    return parser.parse_args()


def main():
    multiprocessing.freeze_support()
    # Harden stdout against UnicodeEncodeError on CP437 terminals (Windows CMD).
    import io
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(errors="replace")
    action_logger._echo_fn = print_dim
    args = _parse_args()

    if args.debug:
        from src.utils.debug_logger import enable_debug_logging, get_debug_logger
        enable_debug_logging()
        get_debug_logger()  # Eagerly initialize: creates file + SESSION START header now

    resize_console_window()
    startup_lhm = None
    pawnio_was_preinstalled = False
    try:
        from src.utils.integrity import verify_integrity
        verify_integrity()

        print_banner()

        print_info("Checking system privileges...")
        try:
            check_admin()
        except AdminRequiredError as e:
            print_error(str(e))
            print_warning("Some features (like Restore Point Creation) will fail without Admin rights.")
            print()

        action_logger.log_session_start()

        from src.utils.pawnio_check import is_pawnio_installed
        pawnio_was_preinstalled = is_pawnio_installed()

        if args.revert:
            from src.pipeline.phase_revert import run_revert_phase
            run_revert_phase()
            return

        startup_lhm, _ = run_startup_thermal_scan()
        menu_loop(startup_lhm)

    except KeyboardInterrupt:
        print_accent("\nCtrl+C detected. Exiting...")
    except Exception as e:
        print_error(f"Fatal unhandled exception: {e}")
        sys.exit(1)
    finally:
        save_default_config()
        post_run_cleanup(startup_lhm, pawnio_was_preinstalled=pawnio_was_preinstalled)
        action_logger.log_session_end()


if __name__ == "__main__":
    main()
