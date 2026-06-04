"""Modal Yes/No dialog for ``prompt_confirm`` calls (model download, soft confirms).

Behavior contract: Yes → True, No / Esc / close → False.
"""

from __future__ import annotations

from src.gui.widgets.dialogs import CardDialog


class ConfirmDialog(CardDialog):
    """V2 confirm dialog: accent icon, restore-point context, Yes/Skip (W/S) buttons.

    Thin specialization of the shared ``CardDialog`` template
    (``src/gui/widgets/dialogs.py``) that preserves the ``yes_btn`` / ``no_btn`` public
    API the pipeline controller, startup coordinator, and WASD tests rely on. Styling
    lives in ``_qss_card_dialog``.
    """

    def __init__(self, title: str, description: str = "", parent=None,
                 yes_label: str = "Yes, Continue", no_label: str = "Skip") -> None:
        super().__init__(
            title,
            description,
            tone="accent",
            primary_label=yes_label,
            secondary_label=no_label,
            modal=True,
            glow=True,
            parent=parent,
        )
        # Back-compat aliases for existing callers + the WASD test fixture.
        self.yes_btn = self.primary_btn
        self.no_btn = self.secondary_btn
        self.setAccessibleName("Confirm dialog")
