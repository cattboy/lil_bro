from datetime import datetime

from .paths import get_action_log_path


class ActionLogger:
    def __init__(self, log_path: str = None):
        if log_path:
            self.log_path = log_path
        else:
            self.log_path = str(get_action_log_path())
                    
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
        from colorama import Style
        print(f"{Style.DIM}  {log_entry}{Style.RESET_ALL}")
            
# Global singleton instance
action_logger = ActionLogger()
