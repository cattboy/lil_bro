import os
from datetime import datetime

from .paths import get_action_log_path


class ActionLogger:
    def __init__(self, log_path: str = None):
        if log_path:
            self.log_path = log_path
        else:
            self.log_path = str(get_action_log_path())

    def log_session_start(self):
        """Write a === separator block to mark the beginning of a new run."""
        from src._version import __version__

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        separator = "=" * 80
        header = f"[{timestamp}] SESSION START  |  lil_bro v{__version__}"

        try:
            existing = os.path.isfile(self.log_path) and os.path.getsize(self.log_path) > 0
            leading_newline = "\n" if existing else ""
            block = f"{leading_newline}{separator}\n{header}\n{separator}\n"
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(block)
        except Exception as e:
            print(f"Failed to write session start to action log: {e}")

        from src.utils.formatting import print_dim
        print_dim(f"  {header}")

    def log_session_end(self):
        """Write a session end marker line."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] SESSION END"

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            print(f"Failed to write session end to action log: {e}")

        from src.utils.formatting import print_dim
        print_dim(f"  {line}")

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
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(log_entry + "\n")
        except Exception as e:
            # Fallback for testing environments
            print(f"Failed to write to action log: {e}")

        # Echo to terminal (dim, non-intrusive)
        from src.utils.formatting import print_dim
        print_dim(f"  {log_entry}")

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
