import os
from ..utils.formatting import print_step, print_step_done, print_info, print_warning
from ..utils.action_logger import action_logger

def _get_temp_targets() -> dict:
    """Returns the canonical map of temp folder names to their paths."""
    user_temp  = os.environ.get('TEMP', '')
    win_temp   = os.environ.get('WINDIR', 'C:\\Windows') + '\\Temp'
    sw_dist    = os.environ.get('WINDIR', 'C:\\Windows') + '\\SoftwareDistribution\\Download'
    local      = os.environ.get('LOCALAPPDATA', 'C:\\Users\\%USERNAME%\\AppData\\Local')
    appdata    = os.environ.get('APPDATA', 'C:\\Users\\%USERNAME%\\AppData\\Roaming')
    programdata = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
    userprofile = os.environ.get('USERPROFILE', 'C:\\Users\\%USERNAME%')
    return {
        "User Temp":                     user_temp,
        "Windows Temp":                  win_temp,
        "Update Cache":                  sw_dist,
        "NVIDIA Shader Cache":           programdata + '\\NVIDIA Corporation\\NV_Cache',
        "NVIDIA GL Cache":               local + '\\NVIDIA\\GLCache',
        "NVIDIA DX Cache":               local + '\\NVIDIA\\DXCache',
        "NVIDIA Compute Cache":          appdata + '\\NVIDIA\\ComputeCache',
        "D3D Cache":                     local + '\\D3DSCache',
        "NVIDIA Per Driver Version DX Cache": userprofile + '\\AppData\\LocalLow\\NVIDIA\\PerDriverVersion\\DXCache',
        "AMD DX Cache":                  local + '\\AMD\\DxCache',
        "AMD DX9 Cache":                 local + '\\AMD\\DX9Cache',
        "AMD Dxc Cache":                 local + '\\AMD\\DxcCache',
        "AMD Ogl Cache":                 local + '\\OglCache',
        "Intel D3D Cache":               local + '\\Microsoft\\D3DSCache',
    }

def get_temp_sizes() -> dict:
    """
    Returns temp folder sizes without any terminal output.
    Used by spec_dumper to collect data silently during the scan phase.
    """
    targets = _get_temp_targets()
    details = {}
    total_bytes = 0
    for name, path in targets.items():
        size_bytes, count = scan_dir_size(path)
        total_bytes += size_bytes
        details[name] = {"path": path, "size_bytes": size_bytes, "file_count": count}
    return {"total_bytes": total_bytes, "details": details}

def analyze_temp_folders(specs: dict) -> dict:
    """
    Pure analyzer. Reads pre-collected temp folder data from specs dict.
    Returns a standardized finding dict — no system calls, no terminal output.
    """
    temp_data = specs.get("TempFolders", {})
    total_bytes = temp_data.get("total_bytes", 0)
    mb = total_bytes / (1024 * 1024)

    if total_bytes > (1024 * 1024 * 1024):
        return {
            "check": "temp_folders",
            "status": "WARNING",
            "current": total_bytes,
            "message": f"Found {mb:.0f} MB of temporary files and caches. Cleanup recommended.",
            "can_auto_fix": True,
        }
    return {
        "check": "temp_folders",
        "status": "OK",
        "current": total_bytes,
        "message": f"Temp folders are clean ({mb:.0f} MB total).",
        "can_auto_fix": False,
    }

def scan_dir_size(path: str) -> tuple[int, int]:
    """Returns (total_bytes, file_count) for a given directory path."""
    total_size = 0
    file_count = 0
    
    if not os.path.exists(path):
        return 0, 0
        
    for dirpath, _, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if not os.path.islink(fp):
                try:
                    total_size += os.path.getsize(fp)
                    file_count += 1
                except (OSError, FileNotFoundError):
                    # Skip files we cannot access (locked by system, permissions, etc)
                    continue
                    
    return total_size, file_count

def _format_size(size_bytes: int) -> str:
    """Formats bytes to MB/GB string."""
    mb = size_bytes / (1024 * 1024)
    if mb > 1024:
        gb = mb / 1024
        return f"{gb:.2f} GB"
    return f"{mb:.2f} MB"

def scan_temp_folders() -> dict:
    """
    Scans common Windows temporary directories and calculates their sizes.
    """
    print_step("Auditing Temporary Folders")
    targets = _get_temp_targets()
    
    results = {}
    total_bloat_bytes = 0
    
    for name, path in targets.items():
        size_bytes, count = scan_dir_size(path)
        total_bloat_bytes += size_bytes
        results[name] = {"path": path, "size_bytes": size_bytes, "file_count": count}
        
    print_step_done(True)
    
    # Format the report
    total_bloat_formatted = _format_size(total_bloat_bytes)
    
    if total_bloat_bytes > (1024 * 1024 * 1024): # Over 1 GB
        print_warning(f"Found {total_bloat_formatted} of temporary files and system bloat across {sum(r['file_count'] for r in results.values())} files.")
    else:
        print_info(f"System is relatively clean. Found {total_bloat_formatted} of temp files.")
        
    for name, data in results.items():
        if data['size_bytes'] > 0:
            print_info(f"  - {name}: {_format_size(data['size_bytes'])} ({data['file_count']} files) -> {data['path']}")
            
    return {"total_bytes": total_bloat_bytes, "details": results}

def clean_temp_folders(details: dict) -> tuple[int, int]:
    """
    Deletes files from the directories specified in the scan details.
    Returns (bytes_freed, files_deleted).
    """
    print_step("Cleaning Temporary Folders")
    bytes_freed = 0
    files_deleted = 0
    
    for name, data in details.items():
        if data['size_bytes'] == 0:
            continue
            
        path = data['path']
        if not os.path.exists(path):
            continue
            
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try:
                        size = os.path.getsize(fp)
                        os.remove(fp)
                        bytes_freed += size
                        files_deleted += 1
                    except (OSError, FileNotFoundError):
                        # Skip files we cannot access or delete
                        continue
                        
    print_step_done(True)
    freed_formatted = _format_size(bytes_freed)
    print_info(f"Successfully cleaned {freed_formatted} across {files_deleted} files.")
    
    if files_deleted > 0:
        action_logger.log_action("Temp Cleaner", f"Deleted {files_deleted} files, recovered {freed_formatted}", "Dirs: " + ", ".join(details.keys()))
        
    return bytes_freed, files_deleted
