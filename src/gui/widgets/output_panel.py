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


from PySide6.QtWidgets import (  # noqa: E402
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

class OutputPanel(QWidget):
    """V2 log panel: toolbar (title + Clear/Copy) + streaming QTextEdit below."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("outputPanel")
        self.setAccessibleName("Pipeline output panel")

        vbox = QVBoxLayout(self)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        # ── Log toolbar ──────────────────────────────────────────────
        toolbar = QFrame()
        toolbar.setObjectName("logToolbar")
        tb_row = QHBoxLayout(toolbar)
        tb_row.setContentsMargins(12, 0, 8, 0)
        tb_row.setSpacing(6)
        toolbar.setFixedHeight(36)

        tb_title = QLabel("PIPELINE LOG")
        tb_title.setObjectName("logToolbarTitle")
        tb_row.addWidget(tb_title)
        tb_row.addStretch()

        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setProperty("logBtn", "true")
        self._clear_btn.setFixedHeight(24)
        self._clear_btn.clicked.connect(self.clear_log)

        self._copy_btn = QPushButton("Copy")
        self._copy_btn.setProperty("logBtn", "true")
        self._copy_btn.setFixedHeight(24)
        self._copy_btn.clicked.connect(self._copy_all)

        tb_row.addWidget(self._clear_btn)
        tb_row.addWidget(self._copy_btn)

        vbox.addWidget(toolbar)

        # ── Log text area ────────────────────────────────────────────
        self._text = QTextEdit()
        self._text.setObjectName("outputPanelText")
        self._text.setReadOnly(True)
        self._text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self._text.setAcceptRichText(True)
        self._text.setAccessibleDescription("Streaming output from the optimization pipeline.")

        vbox.addWidget(self._text, stretch=1)

    # ── Log toolbar actions ────────────────────────────────────────────

    def _copy_all(self) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(self._text.toPlainText())

    # ── Public API (same as before) ────────────────────────────────────

    def append_line(self, text: str) -> None:
        """Append a text line, honoring \\r as a last-line replace."""
        if not text:
            return
        if "\r" in text:
            head, _, tail = text.rpartition("\r")
            if head:
                self._append_html(ansi_to_html(head))
            self._replace_last_line(ansi_to_html(tail))
            return
        self._append_html(ansi_to_html(text))

    def _append_html(self, html: str) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def _replace_last_line(self, html: str) -> None:
        cursor = self._text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.select(QTextCursor.SelectionType.LineUnderCursor)
        cursor.removeSelectedText()
        cursor.insertHtml(html)
        self._text.setTextCursor(cursor)
        self._text.ensureCursorVisible()

    def clear_log(self) -> None:
        """Reset the panel between pipeline runs."""
        self._text.clear()
