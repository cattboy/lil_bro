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
from src.utils.formatting import print_info, print_warning, print_error, print_accent, resize_console_window
from src.utils.errors import AdminRequiredError
from src.bootstrapper import check_admin
from src.pipeline.banner import print_banner
from src.pipeline.menu import menu_loop
from src.pipeline.startup_thermals import run_startup_thermal_scan
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
    return parser.parse_args()


def main():
    multiprocessing.freeze_support()
    args = _parse_args()

    if args.debug:
        from src.utils.debug_logger import enable_debug_logging, get_debug_logger
        enable_debug_logging()
        get_debug_logger()  # Eagerly initialize: creates file + SESSION START header now

    resize_console_window()
    startup_lhm = None
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
        startup_lhm, _ = run_startup_thermal_scan()
        menu_loop()

    except KeyboardInterrupt:
        print_accent("\nCtrl+C detected. Exiting...")
    except Exception as e:
        print_error(f"Fatal unhandled exception: {e}")
        sys.exit(1)
    finally:
        post_run_cleanup(startup_lhm)
        action_logger.log_session_end()


if __name__ == "__main__":
    main()
