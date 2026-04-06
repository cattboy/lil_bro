"""
Animated terminal progress bar with a traveling plasma-sweep glow.

Usage:
    bar = AnimatedProgressBar(total=3, label="Applying fixes")
    bar.start()
    bar.update(1, "Setting refresh rate...")
    bar.update(2, "Switching power plan...")
    bar.update(3, "Cleaning temp files...")
    bar.finish()
"""

import shutil
import sys
import threading
import time

from colorama import Fore, Style

from src.utils.formatting import _ASCII_FALLBACK

_FPS = 10  # animation redraws per second


class AnimatedProgressBar:
    """
    Terminal progress bar with a traveling glow animation.

    The filled portion is rendered in cyan (█). A 3-char magenta glow (▓▒░)
    sweeps left-to-right through the filled region. Unfilled slots are dim (░).
    On non-UTF-8 terminals, falls back to ASCII: # = - .
    """

    def __init__(self, total: int, label: str = "Progress"):
        self.total = max(total, 1)  # guard against division by zero
        self.label = label
        self._current = 0
        self._message = ""
        self._glow_offset = 0
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

        # Compute bar width once at construction
        if sys.stdout.isatty():
            cols = shutil.get_terminal_size(fallback=(80, 24)).columns
            self._bar_width = max(20, min(cols - 40, 50))
        else:
            self._bar_width = 30

        # Unicode vs ASCII character sets
        if _ASCII_FALLBACK:
            self._fill_char = "#"
            self._glow_chars = ["=", "-", "."]
            self._empty_char = "."
            self._bolt = ">"
        else:
            self._fill_char = "\u2588"
            self._glow_chars = ["\u2593", "\u2592", "\u2591"]
            self._empty_char = "\u2591"
            self._bolt = "\u26a1"

    # ── Public API ────────────────────────────────────────────────────────────

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def update(self, step: int, message: str = "") -> None:
        with self._lock:
            self._current = step
            self._message = message

    def finish(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        self._draw(final=True)
        sys.stdout.write("\n")
        sys.stdout.flush()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _animate(self) -> None:
        while self._running:
            self._draw()
            self._glow_offset = (self._glow_offset + 1) % self._bar_width
            time.sleep(1.0 / _FPS)

    def _draw(self, final: bool = False) -> None:
        with self._lock:
            current = self._current
            message = self._message
            glow_offset = self._glow_offset

        filled = int((current / self.total) * self._bar_width)
        pct = int((current / self.total) * 100)

        bar_chars: list[str] = []

        for i in range(self._bar_width):
            if i < filled:
                dist = (i - glow_offset) % filled if filled > 0 else 0
                if dist < len(self._glow_chars):
                    bar_chars.append(f"{Fore.MAGENTA}{self._glow_chars[dist]}{Style.RESET_ALL}")
                else:
                    bar_chars.append(f"{Fore.CYAN}{self._fill_char}{Style.RESET_ALL}")
            else:
                bar_chars.append(f"{Style.DIM}{self._empty_char}{Style.RESET_ALL}")

        bar_str = "".join(bar_chars)
        msg_str = f"  {Style.DIM}{message}{Style.RESET_ALL}" if message else ""
        label_str = f"{Fore.YELLOW}{self._bolt} {self.label}{Style.RESET_ALL}"

        line = f"\r  {label_str}  [{bar_str}] {pct:3d}%{msg_str}"
        sys.stdout.write(line)
        sys.stdout.flush()
