import time
import pytest
from src.utils.progress_bar import AnimatedProgressBar


def test_progress_bar_update():
    """update() + finish() should not crash with normal usage."""
    bar = AnimatedProgressBar(total=3, label="Test")
    bar.start()
    bar.update(1, "step one")
    bar.update(2, "step two")
    bar.update(3, "step three")
    bar.finish()


def test_progress_bar_finish_cleans_up():
    """After finish(), the animation thread should no longer be alive."""
    bar = AnimatedProgressBar(total=2, label="Test")
    bar.start()
    bar.update(1)
    bar.finish()
    assert bar._thread is not None
    assert not bar._thread.is_alive()


def test_progress_bar_zero_total():
    """total=0 should not raise ZeroDivisionError."""
    bar = AnimatedProgressBar(total=0, label="Test")
    bar.start()
    bar.update(0)
    bar.finish()
