import os
import threading
from collections.abc import Callable
from datetime import datetime
from typing import Optional

from .paths import get_action_log_path


class ActionLogger:
    def __init__(self, log_path: str = None, echo_fn: Optional[Callable[[str], None]] = None,
                 gui_notify_fn: Optional[Callable[[], None]] = None):
        if log_path:
            self.log_path = log_path
        else:
            self.log_path = str(get_action_log_path())
        self._lock = threading.Lock()
        self._echo_fn = echo_fn
        self._gui_notify_fn = gui_notify_fn  # set in GUI mode; emits a Qt signal (see CapNotifier)
        self._cap_reached: bool = False

    def _rotate_if_needed(self) -> None:
        # Must be called from inside a self._lock block — does not acquire the lock itself.
        if self._cap_reached:
            return  # already hit cap this session, all writes refused
        _CAP = 100 * 1024 * 1024  # 100 MB
        try:
            if os.path.isfile(self.log_path) and os.path.getsize(self.log_path) >= _CAP:
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.write("[LOG STOPPED — 100 MB cap reached. Remove this file to resume logging.]\n")
                self._cap_reached = True
                if self._echo_fn:
                    self._echo_fn(
                        "[ERROR] lil_bro_actions.log exceeded the 100 MB cap — "
                        "this indicates a bug causing runaway logging. "
                        "Please remove the file and report the issue."
                    )
                # Record the runaway-logging event in the SEPARATE persistent debug log — the
                # action log itself is now frozen and useless for diagnosis.
                try:
                    from src.utils.debug_logger import get_debug_logger
                    get_debug_logger().error(
                        "Action log hit the 100 MB cap — runaway logging suspected; logging halted."
                    )
                except Exception:
                    pass
                # Called under self._lock — MUST stay non-blocking. In GUI mode this only emits a
                # Qt signal (thread-safe from any thread); the dialog renders on the main thread.
                # Guarded so a GUI-notification failure can never corrupt the logging path.
                if self._gui_notify_fn:
                    try:
                        self._gui_notify_fn()
                    except Exception:
                        pass
        except OSError:
            pass

    def log_session_start(self):
        """Write a === separator block to mark the beginning of a new run."""
        from src._version import __version__

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = "=" * 80
        header = f"[{timestamp}] SESSION START  |  lil_bro v{__version__}"

        try:
            with self._lock:
                self._rotate_if_needed()
                if not self._cap_reached:
                    existing = os.path.isfile(self.log_path) and os.path.getsize(self.log_path) > 0
                    leading_newline = "\n" if existing else ""
                    block = f"{leading_newline}{separator}\n{header}\n{separator}\n"
                    with open(self.log_path, "a", encoding="utf-8") as f:
                        f.write(block)
        except Exception as e:
            print(f"Failed to write session start to action log: {e}")

        if self._echo_fn:
            self._echo_fn(f"  {header}")

    def log_session_end(self):
        """Write a session end marker line."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] SESSION END"

        try:
            with self._lock:
                self._rotate_if_needed()
                if not self._cap_reached:
                    with open(self.log_path, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
        except Exception as e:
            print(f"Failed to write session end to action log: {e}")

        if self._echo_fn:
            self._echo_fn(f"  {line}")

    def log_action(self, component: str, action: str, details: str = "", outcome: str = ""):
        """
        Logs a system modification action.

        When outcome is provided the format is:
            [timestamp] [OUTCOME] [component] action | details
        When omitted (backward-compat):
            [timestamp] [component] action | details
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if outcome:
            log_entry = f"[{timestamp}] [{outcome}] [{component}] {action}"
        else:
            log_entry = f"[{timestamp}] [{component}] {action}"
        if details:
            log_entry += f" | {details}"

        try:
            with self._lock:
                self._rotate_if_needed()
                if not self._cap_reached:
                    with open(self.log_path, "a", encoding="utf-8") as f:
                        f.write(log_entry + "\n")
        except Exception as e:
            # Fallback for testing environments
            print(f"Failed to write to action log: {e}")

        if self._echo_fn:
            self._echo_fn(f"  {log_entry}")

    def log_fix_dispatch(self, check: str) -> None:
        """Log that a fix handler is being dispatched."""
        self.log_action("FixDispatch", f"Dispatching fix: {check}")

    def log_fix_result(self, check: str, success: bool, details: str = "") -> None:
        """Log the outcome of a dispatched fix."""
        outcome = "PASS" if success else "FAIL"
        self.log_action("FixDispatch", f"Fix complete: {check}", details=details, outcome=outcome)

    def log_approval_decision(self, approved: list, skipped: list) -> None:
        """Log user approval/skip decisions from the proposal flow."""
        if approved:
            self.log_action("Approval", f"User approved: {', '.join(approved)}", outcome="APPROVED")
        if skipped:
            self.log_action("Approval", f"User skipped: {', '.join(skipped)}", outcome="SKIPPED")
        if not approved and not skipped:
            self.log_action("Approval", "User skipped all fixes", outcome="SKIPPED")


# Global singleton instance
action_logger = ActionLogger()
