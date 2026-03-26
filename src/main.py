"""
lil_bro -- Entry point.

Thin wrapper that handles:
  - multiprocessing freeze_support (PyInstaller)
  - File integrity verification (frozen builds)
  - Admin privilege check
  - Delegates to pipeline.menu for the main loop
"""

import multiprocessing
import sys

from src.utils.formatting import print_info, print_warning, print_error, print_accent, resize_console_window
from src.utils.errors import AdminRequiredError
from src.bootstrapper import check_admin
from src.pipeline.banner import print_banner
from src.pipeline.menu import menu_loop
from src.pipeline.startup_thermals import run_startup_thermal_scan


def main():
    multiprocessing.freeze_support()
    resize_console_window()
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

        startup_lhm, _ = run_startup_thermal_scan()
        try:
            menu_loop()
        finally:
            startup_lhm.stop()

    except KeyboardInterrupt:
        print_accent("\nCtrl+C detected. Exiting...")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal unhandled exception: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
