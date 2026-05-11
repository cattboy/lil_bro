from __future__ import annotations

from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy

from src.gui.widgets.phase_card import PhaseCard

_PHASE_NAMES = [
    "Bootstrap",
    "System Scan",
    "AI Analysis",
    "Apply Fixes",
    "Verify",
]


class PhaseRow(QFrame):
    """Horizontal strip of 5 phase cards shown in the output view."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("phaseRow")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._cards: dict[str, PhaseCard] = {}
        for i, name in enumerate(_PHASE_NAMES, start=1):
            card = PhaseCard(i, name, self)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(card)
            self._cards[name] = card

    def update_phase(self, name: str, status: str, pct: int = 0) -> None:
        """Update a phase card by name. Ignored if name is not a known phase."""
        card = self._cards.get(name)
        if card is None:
            return
        card.set_status(status)
        if status == PhaseCard.STATUS_ACTIVE and pct > 0:
            card.update_progress(pct)

    def reset(self) -> None:
        for card in self._cards.values():
            card.set_status(PhaseCard.STATUS_PENDING)
