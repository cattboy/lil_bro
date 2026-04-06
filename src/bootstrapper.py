import os
import sys
import subprocess
from datetime import datetime
from .utils.errors import AdminRequiredError, RestorePointError
from .utils.formatting import prompt_approval, print_step, print_step_done, print_error, print_success
from .utils.action_logger import action_logger
from .utils.platform import is_admin

def check_admin():
    """Ensure we have admin privileges, or raise an error."""
    if not is_admin():
        raise AdminRequiredError("lil_bro requires Administrator privileges to create restore points and modify system settings. Please restart the application as Administrator.")

def is_system_restore_enabled() -> bool:
    """Checks if System Restore is enabled on the C: drive."""
    ps_command = (
        "$val = Get-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\CurrentVersion\\SystemRestore' -ErrorAction SilentlyContinue; "
        "if ($val -ne $null -and $val.RPSessionInterval -eq 1) { Write-Output 'TRUE' } else { Write-Output 'FALSE' }"
    )
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True, text=True, check=False
        )
        return "TRUE" in result.stdout
    except Exception:
        return False

def enable_system_restore() -> bool:
    """Enables System Restore on the C: drive."""
    ps_command = 'Enable-ComputerRestore -Drive "C:\\"'
    try:
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            action_logger.log_action("System Restore", "Enabled System Restore on C: drive", f"Execution: {ps_command}")
            return True
        return False
    except Exception:
        return False

def create_restore_point(description: str | None = None):
    """
    Creates a Windows System Restore point via PowerShell.
    Require human-in-the-loop approval before executing.
    """
    if description is None:
        description = f"lil_bro Pre-Tuning {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

    if not is_system_restore_enabled():
        print_error("System Restore is currently disabled.")
        print_step("To manually enable: Click Start Button -> Type 'Create a restore point' -> Click Configure -> Turn on system protection. -> Click OK & OK -> Rerun script and try again")
        if prompt_approval("Would you like lil_bro to automatically enable System Restore on the C: drive now?"):
            print_step("Enabling System Restore on C: drive...")
            if enable_system_restore():
                print_step_done(success=True)
                print_success("System Restore enabled successfully.")
            else:
                print_step_done(success=False)
                print_error("Failed to enable System Restore automatically (Administrative privileges may be required).")
                print_error("Please enable it manually and try again.")
                return False
        else:
            print_error("Cannot create a system restore point while System Protection is disabled.")
            return False

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
            action_logger.log_action("System Restore", f"Created Restore Point: {description}", f"Execution: {ps_command}")
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
