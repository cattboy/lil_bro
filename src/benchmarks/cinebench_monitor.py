"""User-facing monitor threads + window manipulation during a benchmark run.

Holds the keyboard abort watcher, the periodic progress printer, and the
ctypes-based Cinebench window minimizer. All three run as background threads
during ``BenchmarkRunner._run_cinebench`` and share an ``abort_event`` for
cancellation.

Note: ``_keyboard_abort_watcher``, ``_benchmark_progress_printer``,
``_minimize_cinebench_window``, ``SW_HIDE``, ``SW_MINIMIZE`` are imported
into ``cinebench`` from this module so that tests patching
``@patch("src.benchmarks.cinebench.<name>")`` intercept the right binding.
The runner code in ``cinebench._run_cinebench`` references these by bare name
so the patches bite.
"""

import os
import threading
import time

import msvcrt

from ..utils.formatting import print_info

# Win32 ShowWindow nCmdShow codes.
SW_HIDE = 0
SW_MINIMIZE = 6


def _keyboard_abort_watcher(abort_event: threading.Event) -> None:
    """
    Background thread -- sets abort_event when Q, q, or Enter is pressed.

    Uses ``msvcrt.kbhit()`` (Windows, no Enter required for Q).  Polls every
    50 ms so it stays responsive without busy-spinning.
    """
    while not abort_event.is_set():
        if msvcrt.kbhit():
            key = msvcrt.getch()
            if key in (b"q", b"Q", b"\r"):
                abort_event.set()
                return
        time.sleep(0.05)


def _benchmark_progress_printer(abort_event: threading.Event, start_time: float) -> None:
    """Prints elapsed time + abort hint every 30 s during a benchmark run."""
    while not abort_event.is_set():
        time.sleep(30)
        if abort_event.is_set():
            break
        elapsed = int(time.monotonic() - start_time)
        mins, secs = divmod(elapsed, 60)
        print_info(f"Still running... [{mins}m {secs:02d}s elapsed]  Press Q or Enter to abort.")


def _minimize_cinebench_window(
    cb_exe: str,
    timeout: float,
    abort_event: threading.Event,
    cmd_parent_pid: int,
) -> None:
    """Minimize the Cinebench GUI once after launch, then leave the user alone.

    Identifies windows by their owning process executable name (e.g.
    ``Cinebench.exe``) rather than by window title. Cinebench 2026 spends
    the first ~100 s with title ``SplashScreen`` (no 'cinebench' substring),
    so title matching misses the splash and only catches the main window
    much later. Process matching catches both within seconds of launch.

    Also hides the helper ``cmd.exe`` process spawned by ``_run_cinebench``
    (identified by ``cmd_parent_pid``) as a belt-and-suspenders fallback in
    case ``STARTUPINFO``/``SW_HIDE`` ever fails to suppress its console
    window at spawn time. cmd windows are SW_HIDE'd (not minimized) so they
    disappear entirely rather than landing in the taskbar.

    Polls every second for up to ``timeout`` to tolerate slow systems. On
    the first match, hides/minimizes the windows and returns -- never
    touches focus again. The OS pops whatever was behind Cinebench
    (typically lil_bro) to the foreground naturally when its windows
    minimize.
    """
    import ctypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    # OpenProcess returns HANDLE (pointer). Without restype set, ctypes
    # defaults to c_int, and a high-bit-set handle would read as a negative
    # int that the `if not h` nullity check would mistake for a valid handle.
    kernel32.OpenProcess.restype = ctypes.c_void_p

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    cb_exe_lower = cb_exe.lower()
    own_pid = kernel32.GetCurrentProcessId()
    # Each entry: (hwnd, show_cmd). show_cmd is SW_MINIMIZE for Cinebench
    # windows and SW_HIDE for our spawned cmd window.
    found: list[tuple[int, int]] = []

    def _window_pid(hwnd) -> int:
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value

    def _belongs_to_cinebench(hwnd):
        pid = _window_pid(hwnd)
        if pid == 0 or pid == own_pid:
            return False
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h:
            return False
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return False
            return os.path.basename(buf.value).lower() == cb_exe_lower
        finally:
            kernel32.CloseHandle(h)

    def _belongs_to_our_cmd(hwnd) -> bool:
        # The outer cmd.exe spawned by subprocess.Popen has pid == cmd_parent_pid.
        # Match windows owned by exactly that pid, regardless of image name.
        pid = _window_pid(hwnd)
        return pid != 0 and pid == cmd_parent_pid

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_size_t, ctypes.c_size_t)

    def _callback(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        if _belongs_to_our_cmd(hwnd):
            found.append((hwnd, SW_HIDE))
        elif _belongs_to_cinebench(hwnd):
            found.append((hwnd, SW_MINIMIZE))
        return True

    callback = WNDENUMPROC(_callback)
    deadline = time.monotonic() + timeout
    while not abort_event.is_set() and time.monotonic() < deadline:
        found.clear()
        user32.EnumWindows(callback, 0)
        if found:
            for hwnd, show_cmd in found:
                user32.ShowWindow(hwnd, show_cmd)
            return  # one-shot -- never meddle with the user's session again
        time.sleep(1)
