import os
from ..utils.formatting import print_step, print_step_done, print_info, print_warning

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
    
    # 1. User Temp
    user_temp = os.environ.get('TEMP', '')
    
    # 2. Windows Temp
    win_temp = os.environ.get('WINDIR', 'C:\\Windows') + '\\Temp'
    
    # 3. Software Distribution Download (Windows Update cache)
    sw_dist = os.environ.get('WINDIR', 'C:\\Windows') + '\\SoftwareDistribution\\Download'
    
    targets = {
        "User Temp": user_temp,
        "Windows Temp": win_temp,
        "Update Cache": sw_dist
    }
    
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
