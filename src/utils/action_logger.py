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

    def log_action(self, component: str, action: str, details: str = ""):
        """
        Logs a system modification action.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
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
            
# Global singleton instance
action_logger = ActionLogger()
