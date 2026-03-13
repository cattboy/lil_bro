import ctypes
import os
import sys
import subprocess
from .utils.errors import AdminRequiredError, RestorePointError
from .utils.formatting import prompt_approval, print_step, print_step_done, print_error, print_success

def is_admin() -> bool:
    """Check if the current process has administrative privileges."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def check_admin():
    """Ensure we have admin privileges, or raise an error."""
    if not is_admin():
        raise AdminRequiredError("lil_bro requires Administrator privileges to create restore points and modify system settings. Please restart the application as Administrator.")

def create_restore_point(description: str = "Antigravity Pre-Tuning Backup"):
    """
    Creates a Windows System Restore point via PowerShell.
    Require human-in-the-loop approval before executing.
    """
    if not prompt_approval(f"Create a System Restore Point ('{description}')? This is highly recommended before any system changes."):
        print_error("System Restore Point creation bypassed by user.")
        return False
        
    print_step("Creating System Restore Point (this may take a minute)")
    
    ps_command = f'Checkpoint-Computer -Description "{description}" -RestorePointType "MODIFY_SETTINGS"'
    
    try:
        # Run the powershell command. Capture output to avoid spamming the console, but check return code.
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
            check=False # We handle the check manually to provide better error messages
        )
        
        if result.returncode == 0:
            print_step_done(success=True)
            print_success(f"Restore point '{description}' created successfully.")
            print_success("If anything goes wrong, you can boot into Windows Recovery Environment and restore this snapshot.")
            return True
        else:
            print_step_done(success=False)
            print_error(f"Failed to create restore point. PowerShell output: {result.stderr.strip()}")
            raise RestorePointError(f"PowerShell returned non-zero exit status: {result.returncode}")
            
    except FileNotFoundError:
        print_step_done(success=False)
        raise RestorePointError("PowerShell executable not found. Ensure PowerShell is installed and in your PATH.")
    except Exception as e:
        print_step_done(success=False)
        raise RestorePointError(f"Unexpected error creating restore point: {e}")
