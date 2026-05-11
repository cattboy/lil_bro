"""QTextEdit subclass that streams pipeline output, translating ANSI/colorama → HTML.

The CLI prints colorama codes (Fore/Style) via the existing ``print_*``
helpers. In GUI mode the bridge installs an output sink that funnels
those same lines into ``OutputPanel.append_line()``; this class
translates the ANSI escape sequences into HTML ``<span>`` colors so the
panel looks like the terminal it replaced.

Carriage-return semantics: ``\\r`` rewinds to start of the current line.
The CLI uses this for in-place redraws (progress bar plasma sweep). We
replicate by treating any text after a ``\\r`` as a replacement for the
last appended line, so the output panel doesn't accumulate a flicker
trail of intermediate frames.
"""

from __future__ import annotations

import re
from html import escape

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QTextEdit


# Colorama Fore/Style codes mapped to DESIGN.md hex colors so the panel
# matches the QSS theme exactly. Background codes (40-47) ignored —
# colorama doesn't use them and Qt's selection background handles
# highlights.
_ANSI_TO_HEX = {
    "30": "#6B6A70",  # BLACK   → text_muted
    "31": "#FF6B6B",  # RED     → error
    "32": "#4ADE80",  # GREEN   → success
    "33": "#FFB547",  # YELLOW  → warning
    "34": "#60A5FA",  # BLUE    → info
    "35": "#D183E8",  # MAGENTA → brand pink
    "36": "#00E5CC",  # CYAN    → accent
    "37": "#E8E6E3",  # WHITE   → text_primary
    "90": "#6B6A70",  # bright BLACK
    "91": "#FF6B6B",  # bright RED
    "92": "#4ADE80",
    "93": "#FFB547",
    "94": "#60A5FA",
    "95": "#D183E8",
    "96": "#00E5CC",
    "97": "#E8E6E3",
}

_ANSI_RE = re.compile(r"\x1b\[([0-9;]*)m")


def ansi_to_html(text: str) -> str:
    """Translate a colorama-tinted line into HTML with span colors."""
    out: list[str] = []
    open_spans = 0
    pos = 0
    for match in _ANSI_RE.finditer(text):
        out.append(escape(text[pos:match.start()]))
        codes = [c for c in match.group(1).split(";") if c]
        for code in codes:
            if code in ("0", ""):
                out.extend(["</span>"] * open_spans)
                open_spans = 0
            elif code == "1":
                out.append('<span style="font-weight:600">')
                open_spans += 1
            elif code == "2":
                out.append('<span style="opacity:0.65">')
                open_spans += 1
            elif code in _ANSI_TO_HEX:
                out.append(f'<span style="color:{_ANSI_TO_HEX[code]}">')
                open_spans += 1
        pos = match.end()
    out.append(escape(text[pos:]))
    out.extend(["</span>"] * open_spans)
    return "".join(out)


class OutputPanel(QTextEdit):
    """Live log panel for the pipeline worker.

    Use ``append_line(text)`` from the main thread (after the worker's
    ``output_emitted`` signal cross-thread hop). Carriage returns trigger
    last-line replacement; otherwise text is appended verbatim.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("outputPanel")
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.setAcceptRichText(True)
        self.setAccessibleName("Pipeline output panel")
        self.setAccessibleDescription("Streaming output from the optimization pipeline.")

    def append_line(self, text: str) -> None:
        """Append a text line, honoring \\r as a last-line replace."""
        if not text:
            return

        # Multiple \r segments: keep only the segment after the final \r as
        # the "current frame" — that's the terminal redraw semantics.
        if "\r" in text:
            head, _, tail = text.rpartition("\r")
            if head:
                self._append_html(ansi_to_html(head))
            self._replace_last_line(ansi_to_html(tail))
            return

        self._append_html(ansi_to_html(text))

    def _append_html(self, html: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _replace_last_line(self, html: str) -> None:
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        cursor.removeSelectedText()
        cursor.insertHtml(html)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def clear_log(self) -> None:
        """Reset the panel between pipeline runs."""
        self.clear()
