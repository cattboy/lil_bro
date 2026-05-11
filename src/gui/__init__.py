"""PySide6 GUI for lil_bro.

The GUI is the default launch mode (``lil_bro.exe`` with no args). The
terminal CLI is preserved verbatim behind ``lil_bro.exe --terminal``.

Architecture: a QThread worker wraps the existing synchronous 5-phase
pipeline; signal/slot bridge converts ``input()``-shaped prompts into
modal Qt dialogs via the ``formatting.set_*_handler`` registry.
"""
