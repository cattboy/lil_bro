"""Shared card-style dialog template for lil_bro's PySide6 GUI.

``CardDialog`` is the single building block for every lil_bro dialog: a DESIGN.md
"card" (surface background, terminal border, 12px radius) with an optional
tone-coloured icon, a title, a description, and a button row carrying a glow-accented
primary action (``W``) and an optional secondary action (``S``). It consolidates the
near-identical scaffolds that ``ConfirmDialog``, ``AdminWarningDialog`` and
``MouseReadyDialog`` used to hand-roll, and replaces the stock ``QMessageBox`` dialogs
(cap warning, debug-log notice) with on-brand cards.

Styling is object-name driven (``#cardDialog`` / ``#cardIcon`` / ``#cardTitle`` /
``#cardDesc`` / ``#cardAccentBar`` — see ``_qss_card_dialog`` in
``src/gui/theme/stylesheet_dialogs.py``). The icon tint is driven by the dynamic
``cardTone`` property (``accent`` | ``warning`` | ``error`` | ``info`` | ``success``) —
deliberately *not* the ``sev`` property (reserved for ``low``/``medium``/``high``
severity) nor ``statTone``.

Every new dialog MUST be built from ``CardDialog`` — never a raw ``QMessageBox`` or a
hand-rolled ``QDialog``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

__all__ = ["CardDialog"]

# Default glyph per tone. Callers may override via ``icon=``; the emoji are an interim
# stand-in (tokens.py discourages emoji as design elements — a QIcon migration is
# tracked in TODOS), so this map stays the single source of icon truth.
_TONE_GLYPH: dict[str, str] = {
    "accent": "⚡",
    "warning": "⚠",
    "error": "⚠",
    "info": "ⓘ",
    "success": "✓",
}

# Sentinel for "derive the glyph from cardTone". Distinct from ``None`` (= no icon).
_DERIVE = object()


class CardDialog(QDialog):
    """DESIGN.md card dialog: optional icon + title + description + W/S buttons.

    Args:
        title: Card heading (also the window title and default accessible name).
        description: Body text; hidden when empty.
        tone: Icon tint — ``accent`` | ``warning`` | ``error`` | ``info`` | ``success``.
        icon: Glyph to show; defaults to deriving one from ``tone``. Pass ``None``
            (or use ``accent_bar``) for no icon.
        primary_label: Text of the accent ``(W)`` button (always present).
        secondary_label: Text of the ``(S)`` button; ``None`` => single-button
            acknowledgement (Esc accepts) instead of a two-button choice (Esc rejects).
        modal: Whether the dialog blocks (``.exec()``) or is shown non-modally.
        glow: Apply the accent drop-shadow glow to the primary button.
        accent_bar: Render a 2px accent bar at the top instead of an icon
            (the MouseReadyDialog variant).
        parent: Qt parent.
    """

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        tone: str = "accent",
        icon: object = _DERIVE,
        primary_label: str = "OK",
        secondary_label: str | None = None,
        modal: bool = True,
        glow: bool = True,
        accent_bar: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cardDialog")
        self.setProperty("cardTone", tone)
        self.setWindowTitle(title)
        self.setModal(modal)
        self.setFixedWidth(420)
        self.setAccessibleName(title)
        self.setAccessibleDescription(description or title)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(16)

        if accent_bar:
            bar = QFrame()
            bar.setObjectName("cardAccentBar")
            bar.setFixedHeight(2)
            layout.addWidget(bar)

        # -- Icon + text row ------------------------------------------------
        glyph = _TONE_GLYPH.get(tone, "") if icon is _DERIVE else icon
        body_row = QHBoxLayout()
        body_row.setSpacing(14)
        body_row.setAlignment(Qt.AlignmentFlag.AlignTop)

        if glyph:
            icon_lbl = QLabel(glyph)
            icon_lbl.setObjectName("cardIcon")
            icon_lbl.setProperty("cardTone", tone)
            icon_lbl.setAlignment(
                Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
            )
            body_row.addWidget(icon_lbl, alignment=Qt.AlignmentFlag.AlignTop)

        text_col = QVBoxLayout()
        text_col.setSpacing(6)

        title_lbl = QLabel(title)
        title_lbl.setObjectName("cardTitle")
        title_lbl.setWordWrap(True)
        text_col.addWidget(title_lbl)

        self._desc_lbl = QLabel(description)
        self._desc_lbl.setObjectName("cardDesc")
        self._desc_lbl.setWordWrap(True)
        if not description:
            self._desc_lbl.hide()
        text_col.addWidget(self._desc_lbl)

        body_row.addLayout(text_col)
        layout.addLayout(body_row)

        # -- Buttons --------------------------------------------------------
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.secondary_btn: QPushButton | None = None
        if secondary_label is not None:
            self.secondary_btn = QPushButton(f"{secondary_label} (S)")
            self.secondary_btn.setObjectName("secondary")
            # Secondary must not auto-default, or the WASD filter's W (= click the
            # default button) can fire reject() when it holds the initial focus.
            self.secondary_btn.setAutoDefault(False)
            self.secondary_btn.clicked.connect(self.reject)
            btn_row.addWidget(self.secondary_btn)

        self.primary_btn = QPushButton(f"{primary_label} (W)")
        self.primary_btn.setObjectName("primary")
        self.primary_btn.setDefault(True)
        self.primary_btn.clicked.connect(self.accept)
        if glow:
            # DESIGN.md "primary accent elements get a soft glow"; QSS can't do
            # box-shadow, so use a drop-shadow effect with the accent colour.
            effect = QGraphicsDropShadowEffect(self)
            effect.setBlurRadius(24)
            effect.setColor(QColor(0, 229, 204, 150))  # accent #00E5CC, soft alpha
            effect.setOffset(0, 0)
            self.primary_btn.setGraphicsEffect(effect)
        btn_row.addWidget(self.primary_btn)
        layout.addLayout(btn_row)

    def keyPressEvent(self, event):  # noqa: N802  Qt override
        if event.key() == Qt.Key.Key_Escape:
            # Single-button card = acknowledgement -> accept; two-button = choice -> reject.
            if self.secondary_btn is not None:
                self.reject()
            else:
                self.accept()
            return
        super().keyPressEvent(event)
