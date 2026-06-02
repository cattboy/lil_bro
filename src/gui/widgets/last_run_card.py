"""Read-only Dashboard card listing the fixes applied this session.

Mirrors the on-disk session manifest (``load_manifest`` in ``src.utils.revert``):
one row per applied fix, showing the fix name + time, the before->after
transition (when the manifest stored one), and whether the fix can be reverted.
The card never triggers a revert itself -- revert stays in the dedicated
``run_revert_phase`` / ``RevertWorker`` flow. It is a faithful view of the same
artifact the revert flow consumes, so card and undo can never disagree.

Refresh is driven externally: ``StartupCoordinator`` seeds it at startup and a
``QFileSystemWatcher`` on the backups dir re-feeds it on every fix/revert.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.gui.theme import repolish

# Human-readable titles for the 5 registered fix checks (the @register_fix keys
# in src/pipeline/fix_dispatch.py). Unknown checks fall back to a title-cased slug.
_FIX_LABELS: dict[str, str] = {
    "game_mode": "Game Mode",
    "power_plan": "Power Plan",
    "display": "Display Refresh Rate",
    "nvidia_profile": "NVIDIA Profile",
    "temp_folders": "Temp Folders",
}

# Non-revertible reasons longer than this are elided in the row (full text on hover).
_MAX_REASON_LEN = 64


def _fix_label(fix: str) -> str:
    return _FIX_LABELS.get(fix, fix.replace("_", " ").title())


def _fmt_date(value: object) -> str:
    """ISO -> 'YYYY-MM-DD HH:MM', or '-' on missing/unparseable input."""
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return "—"


def _fmt_time(value: object) -> str:
    """ISO -> 'HH:MM:SS', or '-' on missing/unparseable input."""
    try:
        return datetime.fromisoformat(str(value)).strftime("%H:%M:%S")
    except (TypeError, ValueError):
        return "—"


# ── before->after transition formatters (one per fix type) ──────────────────
#
# Each receives the entry's `before` and `after` dicts (both already confirmed to
# be dicts by _format_transition) and returns a display string. nvidia_profile is
# intentionally absent: it is revertible but records only `before_backup` (a file
# path), no before/after pair, so it gets no transition text. Non-revertible fixes
# (temp_folders) also have no before/after.

def _fmt_game_mode(before: dict, after: dict) -> str:
    b = "On" if before.get("AutoGameModeEnabled") else "Off"
    a = "On" if after.get("AutoGameModeEnabled") else "Off"
    return f"Game Mode: {b} → {a}"


def _fmt_power_plan(before: dict, after: dict) -> str:
    return f"{before.get('name') or '?'} → {after.get('name') or '?'}"


def _fmt_display(before: dict, after: dict) -> str:
    b_hz = int(before.get("hz") or 0)
    a_hz = int(after.get("hz") or 0)
    if not b_hz or not a_hz:
        return ""
    text = f"{b_hz} Hz → {a_hz} Hz"
    b_res = (before.get("width"), before.get("height"))
    a_res = (after.get("width"), after.get("height"))
    if all(b_res) and all(a_res) and b_res != a_res:
        text += f"  ({b_res[0]}×{b_res[1]} → {a_res[0]}×{a_res[1]})"
    return text


_TRANSITION_FORMATTERS: dict[str, Callable[[dict, dict], str]] = {
    "game_mode": _fmt_game_mode,
    "power_plan": _fmt_power_plan,
    "display": _fmt_display,
}


def _format_transition(entry: dict) -> str:
    """Return a 'before -> after' string for an entry, or '' when none applies.

    Uses .get() throughout: a revertible nvidia_profile entry has no before/after
    keys at all, so a missing key must yield '' rather than raising KeyError.
    """
    before = entry.get("before")
    after = entry.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        return ""
    fn = _TRANSITION_FORMATTERS.get(str(entry.get("fix")))
    if fn is None:
        return ""
    try:
        return fn(before, after)
    except (TypeError, ValueError):
        return ""


class LastRunCard(QFrame):
    """Read-only list of applied fixes. Populated via ``set_manifest``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("lastRunCard")
        self.setAccessibleName("Applied fixes card")

        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(8)

        self._header = QLabel("APPLIED FIXES")
        self._header.setObjectName("pollLabel")
        root.addWidget(self._header)

        # System-restore availability line (sev-tinted).
        self._restore_lbl = QLabel("")
        self._restore_lbl.setObjectName("pollStatus")
        root.addWidget(self._restore_lbl)

        # Container the per-fix rows are added to / torn down from.
        self._rows_box = QVBoxLayout()
        self._rows_box.setSpacing(6)
        root.addLayout(self._rows_box)

        # Row container widgets, tracked so they can be torn down with
        # deleteLater on each refresh (mirrors Dashboard._rebuild_monitor_cards).
        self._rows: list[QWidget] = []

    # ── public API ──────────────────────────────────────────────────────
    def set_manifest(self, manifest: object) -> bool:
        """Render the manifest. Returns True if the card has content to show.

        Defensive against raw on-disk data: a non-dict, an unknown
        ``schema_version``, or an empty/absent ``fixes`` list all render nothing
        and return False (the caller then hides the card).
        """
        self._clear_rows()

        if not isinstance(manifest, dict):
            return False
        if manifest.get("schema_version") not in (None, 1):
            return False
        fixes = manifest.get("fixes") or []
        if not isinstance(fixes, list) or not fixes:
            return False

        self._header.setText(f"APPLIED FIXES — since {_fmt_date(manifest.get('session_date'))}")

        if manifest.get("restore_point_created"):
            self._restore_lbl.setText("✓ System Restore point available")
            self._restore_lbl.setProperty("sev", "low")
        else:
            self._restore_lbl.setText("⚠ No restore point this session")
            self._restore_lbl.setProperty("sev", "medium")
        repolish(self._restore_lbl)

        for entry in fixes:
            if isinstance(entry, dict):
                self._rows.append(self._build_row(entry))
        return True

    # ── internals ───────────────────────────────────────────────────────
    def _clear_rows(self) -> None:
        for row in self._rows:
            self._rows_box.removeWidget(row)
            row.deleteLater()
        self._rows = []

    def _build_row(self, entry: dict) -> QWidget:
        revertible = bool(entry.get("revertible"))

        row = QWidget(self)
        row.setObjectName("lastRunRow")
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(8)

        # Left column: fix name (primary), then a muted time + transition sub-line.
        left = QVBoxLayout()
        left.setSpacing(2)
        name_lbl = QLabel(_fix_label(str(entry.get("fix", ""))))
        left.addWidget(name_lbl)

        sub_parts: list[str] = []
        applied = _fmt_time(entry.get("applied_at"))
        if applied != "—":
            sub_parts.append(applied)
        transition = _format_transition(entry)
        if transition:
            sub_parts.append(transition)
        if sub_parts:
            sub_lbl = QLabel("  ·  ".join(sub_parts))
            sub_lbl.setObjectName("pollStatus")
            left.addWidget(sub_lbl)
        h.addLayout(left)

        h.addStretch()

        # Right column: revert-status badge, plus the inline reason when non-revertible.
        right = QVBoxLayout()
        right.setSpacing(2)
        badge = QLabel("Revertible" if revertible else "Not revertible")
        badge.setObjectName("pollStatus")
        badge.setProperty("sev", "low" if revertible else "medium")
        repolish(badge)
        right.addWidget(badge, alignment=Qt.AlignmentFlag.AlignRight)

        if not revertible:
            reason = str(entry.get("reason") or entry.get("display") or "")
            if reason:
                shown = reason if len(reason) <= _MAX_REASON_LEN else reason[: _MAX_REASON_LEN - 1] + "…"
                reason_lbl = QLabel(shown)
                reason_lbl.setObjectName("pollStatus")
                reason_lbl.setToolTip(reason)
                right.addWidget(reason_lbl, alignment=Qt.AlignmentFlag.AlignRight)
        h.addLayout(right)

        self._rows_box.addWidget(row)
        return row
