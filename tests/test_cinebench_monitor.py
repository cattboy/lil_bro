"""Tests for src.benchmarks.cinebench_monitor.

The monitor module holds three background-thread helpers plus the Win32
ShowWindow constants. These tests drive each helper directly (never as a real
thread) with ``time.sleep`` and ``msvcrt`` patched at the module's own
bindings so they run instantly and never block on real keyboard / clock input.
"""

import threading
from unittest.mock import patch, MagicMock

from src.benchmarks.cinebench_monitor import (
    _keyboard_abort_watcher,
    _benchmark_progress_printer,
    _minimize_cinebench_window,
    SW_HIDE,
    SW_MINIMIZE,
)


# ── SW_* constants ────────────────────────────────────────────────────────────

def test_sw_hide_constant_value():
    """SW_HIDE must equal the Win32 ShowWindow nCmdShow code 0."""
    assert SW_HIDE == 0


def test_sw_minimize_constant_value():
    """SW_MINIMIZE must equal the Win32 ShowWindow nCmdShow code 6."""
    assert SW_MINIMIZE == 6


# ── _keyboard_abort_watcher ───────────────────────────────────────────────────

@patch("src.benchmarks.cinebench_monitor.time.sleep")
@patch("src.benchmarks.cinebench_monitor.msvcrt")
def test_keyboard_abort_watcher_sets_event_on_q(mock_msvcrt, mock_sleep):
    """Pressing 'q' sets the abort_event and the watcher returns."""
    mock_msvcrt.kbhit.return_value = True
    mock_msvcrt.getch.return_value = b"q"

    abort_event = threading.Event()
    _keyboard_abort_watcher(abort_event)

    assert abort_event.is_set()


@patch("src.benchmarks.cinebench_monitor.time.sleep")
@patch("src.benchmarks.cinebench_monitor.msvcrt")
def test_keyboard_abort_watcher_sets_event_on_enter(mock_msvcrt, mock_sleep):
    """Pressing Enter (carriage return) also triggers abort."""
    mock_msvcrt.kbhit.return_value = True
    mock_msvcrt.getch.return_value = b"\r"

    abort_event = threading.Event()
    _keyboard_abort_watcher(abort_event)

    assert abort_event.is_set()


@patch("src.benchmarks.cinebench_monitor.time.sleep")
@patch("src.benchmarks.cinebench_monitor.msvcrt")
def test_keyboard_abort_watcher_ignores_unrelated_keys(mock_msvcrt, mock_sleep):
    """An unrelated keypress does not abort; the loop polls, then exits.

    A pressed key that is not q/Q/Enter must NOT set the event. We let the
    loop run exactly one polling iteration by having the externally-set abort
    flag flip on the first ``time.sleep`` so the ``while not is_set()`` guard
    ends the loop without the keypress having caused the abort.
    """
    mock_msvcrt.kbhit.return_value = True
    mock_msvcrt.getch.return_value = b"x"  # not an abort key

    abort_event = threading.Event()

    # Flip the event from the OUTSIDE on the first sleep so the loop terminates
    # after one iteration. If the 'x' keypress had set it, getch would be the
    # cause — instead the sleep side-effect is, proving 'x' was ignored.
    def stop_after_first(_seconds):
        abort_event.set()

    mock_sleep.side_effect = stop_after_first
    _keyboard_abort_watcher(abort_event)

    # getch was called (key was read) but the abort came from our side-effect,
    # so a single getch of 'x' must not have short-circuited via return.
    mock_msvcrt.getch.assert_called_once()
    mock_sleep.assert_called_once()


@patch("src.benchmarks.cinebench_monitor.time.sleep")
@patch("src.benchmarks.cinebench_monitor.msvcrt")
def test_keyboard_abort_watcher_exits_when_event_preset(mock_msvcrt, mock_sleep):
    """A pre-set abort_event short-circuits the loop with no key reads at all."""
    abort_event = threading.Event()
    abort_event.set()

    _keyboard_abort_watcher(abort_event)

    mock_msvcrt.kbhit.assert_not_called()
    mock_sleep.assert_not_called()


# ── _benchmark_progress_printer ───────────────────────────────────────────────

@patch("src.benchmarks.cinebench_monitor.print_info")
@patch("src.benchmarks.cinebench_monitor.time")
def test_progress_printer_emits_elapsed_line(mock_time, mock_print_info):
    """One alive iteration prints an elapsed-time progress line.

    ``time.sleep`` is a no-op; ``time.monotonic`` is staged so the elapsed
    delta is a known 90 s (1m 30s). The abort_event flips after the first
    print so the loop runs exactly once.
    """
    mock_time.sleep.return_value = None
    # start_time=0; first monotonic() inside the body returns 90.
    mock_time.monotonic.return_value = 90.0

    abort_event = threading.Event()

    def stop_after_print(msg):
        abort_event.set()

    mock_print_info.side_effect = stop_after_print
    _benchmark_progress_printer(abort_event, start_time=0.0)

    mock_print_info.assert_called_once()
    printed = mock_print_info.call_args.args[0]
    assert "1m 30s" in printed
    assert "abort" in printed.lower()


@patch("src.benchmarks.cinebench_monitor.print_info")
@patch("src.benchmarks.cinebench_monitor.time")
def test_progress_printer_exits_when_event_preset(mock_time, mock_print_info):
    """A pre-set abort_event keeps the printer silent (loop never entered)."""
    abort_event = threading.Event()
    abort_event.set()

    _benchmark_progress_printer(abort_event, start_time=0.0)

    mock_time.sleep.assert_not_called()
    mock_print_info.assert_not_called()


@patch("src.benchmarks.cinebench_monitor.print_info")
@patch("src.benchmarks.cinebench_monitor.time")
def test_progress_printer_aborts_during_sleep_without_printing(mock_time, mock_print_info):
    """If abort fires DURING the 30s sleep, the printer breaks before printing.

    The loop enters (event unset at the guard), sleeps, then re-checks the
    event before printing. Setting the event from the sleep side-effect must
    take the ``break`` branch — no progress line emitted.
    """
    def set_during_sleep(_seconds):
        abort_event.set()

    mock_time.sleep.side_effect = set_during_sleep

    abort_event = threading.Event()
    _benchmark_progress_printer(abort_event, start_time=0.0)

    mock_time.sleep.assert_called_once()
    mock_print_info.assert_not_called()


# ── _minimize_cinebench_window ────────────────────────────────────────────────

def test_minimize_window_short_circuits_on_preset_abort():
    """A pre-set abort_event returns immediately without touching Win32 APIs.

    The helper checks ``abort_event`` before its first EnumWindows call, so a
    pre-set event means no ctypes calls and a near-instant return. We assert
    on speed (the loop's only ``sleep`` is 1s) rather than mocking ctypes.
    """
    import time

    abort_event = threading.Event()
    abort_event.set()

    start = time.monotonic()
    _minimize_cinebench_window("Cinebench.exe", 60.0, abort_event, cmd_parent_pid=4242)
    elapsed = time.monotonic() - start

    assert elapsed < 0.5, f"helper did not short-circuit on preset abort ({elapsed:.3f}s)"


def test_minimize_window_hides_cmd_and_minimizes_cinebench(monkeypatch):
    """Integration: cmd-pid window → SW_HIDE; cinebench-image window → SW_MINIMIZE.

    Drives a fully-mocked ``ctypes.windll`` through one EnumWindows pass over
    four synthetic hwnds and asserts the correct nCmdShow code per window, and
    that invisible / self-owned windows are skipped entirely.
    """
    import ctypes
    import types

    CMD_HWND, CB_HWND, INVISIBLE_HWND, OWN_HWND = 100, 200, 300, 400
    CMD_PID, CB_PID, OWN_PID = 1234, 5678, 9999

    hwnd_to_pid = {
        CMD_HWND: CMD_PID,
        CB_HWND: CB_PID,
        INVISIBLE_HWND: 7777,
        OWN_HWND: OWN_PID,
    }

    fake_user32 = MagicMock()
    fake_kernel32 = MagicMock()
    fake_kernel32.GetCurrentProcessId.return_value = OWN_PID
    fake_user32.IsWindowVisible.side_effect = lambda hwnd: hwnd != INVISIBLE_HWND

    def gwtpid(hwnd, pid_ref):
        pid_ref._obj.value = hwnd_to_pid.get(hwnd, 0)
        return 1

    fake_user32.GetWindowThreadProcessId.side_effect = gwtpid
    fake_kernel32.OpenProcess.return_value = 0x1000  # non-null handle
    fake_kernel32.CloseHandle.return_value = 1

    def qfpin(handle, flags, buf, size):
        buf.value = r"C:\Path\Cinebench.exe"
        return 1

    fake_kernel32.QueryFullProcessImageNameW.side_effect = qfpin

    def enum_side_effect(callback, lparam):
        callback(CMD_HWND, 0)
        callback(CB_HWND, 0)
        callback(INVISIBLE_HWND, 0)
        callback(OWN_HWND, 0)
        return 1

    fake_user32.EnumWindows.side_effect = enum_side_effect

    fake_windll = types.SimpleNamespace(user32=fake_user32, kernel32=fake_kernel32)
    monkeypatch.setattr(ctypes, "windll", fake_windll)

    abort_event = threading.Event()
    _minimize_cinebench_window("Cinebench.exe", 2.0, abort_event, cmd_parent_pid=CMD_PID)

    show_calls = [c.args for c in fake_user32.ShowWindow.call_args_list]
    assert (CMD_HWND, SW_HIDE) in show_calls, f"cmd hwnd not SW_HIDE'd; got {show_calls}"
    assert (CB_HWND, SW_MINIMIZE) in show_calls, f"cb hwnd not SW_MINIMIZE'd; got {show_calls}"
    shown_hwnds = {c[0] for c in show_calls}
    assert INVISIBLE_HWND not in shown_hwnds
    assert OWN_HWND not in shown_hwnds


def test_minimize_window_polls_until_window_appears(monkeypatch):
    """When no target window exists on the first pass, the helper sleeps and retries.

    First EnumWindows pass finds nothing; ``time.sleep`` is patched to flip the
    abort_event so the loop exits after exactly one retry interval — proving the
    poll-and-sleep path is exercised without a real 1s wait.
    """
    import ctypes
    import types

    fake_user32 = MagicMock()
    fake_kernel32 = MagicMock()
    fake_kernel32.GetCurrentProcessId.return_value = 9999
    fake_user32.EnumWindows.side_effect = lambda callback, lparam: 1  # finds nothing

    fake_windll = types.SimpleNamespace(user32=fake_user32, kernel32=fake_kernel32)
    monkeypatch.setattr(ctypes, "windll", fake_windll)

    abort_event = threading.Event()

    def stop_during_sleep(_seconds):
        abort_event.set()

    with patch("src.benchmarks.cinebench_monitor.time.sleep", side_effect=stop_during_sleep) as mock_sleep:
        _minimize_cinebench_window("Cinebench.exe", 60.0, abort_event, cmd_parent_pid=4242)

    # No window matched -> ShowWindow never called, but we did poll + sleep once.
    fake_user32.ShowWindow.assert_not_called()
    mock_sleep.assert_called_once()
