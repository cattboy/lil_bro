"""Modal confirmation dialog shown before mouse polling measurement in the pipeline.

Blocks the pipeline worker thread until the user clicks OK. Esc also accepts —
there is no meaningful skip because the pipeline always runs the measurement.
"""

from __future__ import annotations

from src.gui.widgets.dialogs import CardDialog


class MouseReadyDialog(CardDialog):
    """Single-action dialog prompting the user to start moving their mouse.

    Thin specialization of the shared ``CardDialog`` template using the accent-bar
    variant (no icon). Styling lives in ``_qss_card_dialog``.
    """

    def __init__(self, parent=None) -> None:
        super().__init__(
            "Mouse Polling Check",
            "We need 2 seconds of mouse movement to measure your polling rate.\n\n"
            "Click the button below and start wiggling your mouse — "
            "the measurement begins immediately.",
            tone="accent",
            icon=None,
            accent_bar=True,
            primary_label="OK — Start Moving Mouse",
            modal=True,
            glow=False,
            parent=parent,
        )
        self.setAccessibleName("Mouse ready dialog")
