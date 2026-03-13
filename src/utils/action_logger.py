import os
from datetime import datetime

class ActionLogger:
    def __init__(self, log_path: str = None):
        repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.log_path = os.path.join(repo_root, "logs", "lil_bro_actions.log")
        
        # Ensure directory exists if not running on Linux dummy environment
        if not self.log_path.startswith('/'):
            log_dir = os.path.dirname(self.log_path)
            if log_dir and not os.path.exists(log_dir):
                try:
                    os.makedirs(log_dir, exist_ok=True)
                except Exception:
                    pass
                    
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
            
# Global singleton instance
action_logger = ActionLogger()
