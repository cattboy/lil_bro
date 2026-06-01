"""Tests for the read-only Applied Fixes dashboard card (T-016).

Pure transition formatters are tested directly (no Qt). Widget rendering uses
the offscreen Qt platform (conftest.py) + qtbot. Visibility is asserted with
``not isHidden()`` rather than ``isVisible()`` — the offscreen platform returns
isVisible()==False for a widget whose parent was never shown.
"""
from __future__ import annotations

from unittest.mock import patch

from PySide6.QtWidgets import QLabel

from src.gui.widgets.last_run_card import (
    LastRunCard,
    _format_transition,
    _fix_label,
)


def _texts(card: LastRunCard) -> list[str]:
    return [lbl.text() for lbl in card.findChildren(QLabel)]


def _make_card(qtbot) -> LastRunCard:
    with patch("src.gui.widgets.last_run_card.repolish"):
        card = LastRunCard()
    qtbot.addWidget(card)
    return card


# ── pure transition formatter ───────────────────────────────────────────────
class TestFormatTransition:
    def test_display_hz(self):
        entry = {"fix": "display", "before": {"hz": 60}, "after": {"hz": 144}}
        assert _format_transition(entry) == "60 Hz → 144 Hz"

    def test_display_includes_resolution_when_changed(self):
        entry = {
            "fix": "display",
            "before": {"hz": 60, "width": 1920, "height": 1080},
            "after": {"hz": 144, "width": 2560, "height": 1440},
        }
        out = _format_transition(entry)
        assert "60 Hz → 144 Hz" in out
        assert "1920×1080 → 2560×1440" in out

    def test_power_plan_names(self):
        entry = {
            "fix": "power_plan",
            "before": {"name": "Balanced"},
            "after": {"name": "High Performance"},
        }
        assert _format_transition(entry) == "Balanced → High Performance"

    def test_game_mode_off_on(self):
        entry = {
            "fix": "game_mode",
            "before": {"AutoGameModeEnabled": 0},
            "after": {"AutoGameModeEnabled": 1},
        }
        assert _format_transition(entry) == "Game Mode: Off → On"

    def test_nvidia_profile_has_no_transition(self):
        """nvidia_profile is revertible but stores only before_backup (no
        before/after) — the formatter must return '' and never raise."""
        entry = {
            "fix": "nvidia_profile",
            "revertible": True,
            "before_backup": r"C:\lil_bro_backups\nvidia_profile_x.nip",
        }
        assert _format_transition(entry) == ""

    def test_non_revertible_has_no_transition(self):
        entry = {"fix": "temp_folders", "revertible": False,
                 "display": "temp files deleted — files gone"}
        assert _format_transition(entry) == ""

    def test_missing_before_after_keys_no_crash(self):
        assert _format_transition({"fix": "display"}) == ""

    def test_bad_numeric_data_no_crash(self):
        entry = {"fix": "display", "before": {"hz": "x"}, "after": {"hz": None}}
        assert _format_transition(entry) == ""


class TestFixLabel:
    def test_known(self):
        assert _fix_label("power_plan") == "Power Plan"

    def test_unknown_falls_back_to_titlecase(self):
        assert _fix_label("some_new_check") == "Some New Check"


# ── set_manifest gating ──────────────────────────────────────────────────────
class TestSetManifestGating:
    def test_none_returns_false(self, qtbot):
        card = _make_card(qtbot)
        assert card.set_manifest(None) is False
        assert card._rows == []

    def test_empty_fixes_returns_false(self, qtbot):
        card = _make_card(qtbot)
        assert card.set_manifest({"schema_version": 1, "fixes": []}) is False

    def test_unknown_schema_version_returns_false(self, qtbot):
        card = _make_card(qtbot)
        m = {"schema_version": 2, "fixes": [{"fix": "display", "revertible": True}]}
        assert card.set_manifest(m) is False
        assert card._rows == []

    def test_non_dict_returns_false(self, qtbot):
        card = _make_card(qtbot)
        assert card.set_manifest("nope") is False


# ── rendering ────────────────────────────────────────────────────────────────
class TestRendering:
    def _manifest(self, **over):
        m = {
            "schema_version": 1,
            "session_date": "2026-06-01T14:30:22.123456",
            "restore_point_created": True,
            "fixes": [
                {"fix": "display", "revertible": True,
                 "applied_at": "2026-06-01T14:30:25",
                 "before": {"hz": 60}, "after": {"hz": 144}},
                {"fix": "temp_folders", "revertible": False,
                 "applied_at": "2026-06-01T14:30:29",
                 "reason": "Deleted temp files cannot be restored"},
            ],
        }
        m.update(over)
        return m

    def test_row_count_matches_fixes(self, qtbot):
        card = _make_card(qtbot)
        with patch("src.gui.widgets.last_run_card.repolish"):
            assert card.set_manifest(self._manifest()) is True
        assert len(card._rows) == 2

    def test_header_shows_session_date(self, qtbot):
        card = _make_card(qtbot)
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(self._manifest())
        assert "2026-06-01 14:30" in card._header.text()

    def test_restore_point_available_line(self, qtbot):
        card = _make_card(qtbot)
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(self._manifest(restore_point_created=True))
        assert "available" in card._restore_lbl.text()
        assert card._restore_lbl.property("sev") == "low"

    def test_restore_point_absent_line(self, qtbot):
        card = _make_card(qtbot)
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(self._manifest(restore_point_created=False))
        assert "No restore point" in card._restore_lbl.text()
        assert card._restore_lbl.property("sev") == "medium"

    def test_transition_and_badges_rendered(self, qtbot):
        card = _make_card(qtbot)
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(self._manifest())
        texts = _texts(card)
        assert any("60 Hz → 144 Hz" in t for t in texts)
        assert "Revertible" in texts
        assert "Not revertible" in texts
        # non-revertible reason rendered inline (not just tooltip)
        assert any("Deleted temp files" in t for t in texts)

    def test_missing_applied_at_and_session_date_render_dash(self, qtbot):
        card = _make_card(qtbot)
        m = {
            "schema_version": 1,
            "fixes": [{"fix": "display", "revertible": True,
                       "before": {"hz": 60}, "after": {"hz": 144}}],
        }
        with patch("src.gui.widgets.last_run_card.repolish"):
            assert card.set_manifest(m) is True
        assert "—" in card._header.text()  # session_date missing

    def test_long_reason_is_elided(self, qtbot):
        card = _make_card(qtbot)
        long = "x" * 200
        m = {"schema_version": 1, "session_date": "2026-06-01T00:00:00",
             "fixes": [{"fix": "temp_folders", "revertible": False, "reason": long}]}
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(m)
        elided = [t for t in _texts(card) if t.endswith("…")]
        assert elided and len(elided[0]) < len(long)

    def test_set_manifest_twice_rebuilds_exact_rows(self, qtbot):
        """Second call tears down old rows; row count reflects only the 2nd manifest."""
        card = _make_card(qtbot)
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(self._manifest())  # 2 fixes
            single = {"schema_version": 1, "session_date": "2026-06-01T00:00:00",
                      "fixes": [{"fix": "game_mode", "revertible": True,
                                 "before": {"AutoGameModeEnabled": 0},
                                 "after": {"AutoGameModeEnabled": 1}}]}
            assert card.set_manifest(single) is True
        assert len(card._rows) == 1

    def test_unknown_fix_uses_fallback_label(self, qtbot):
        card = _make_card(qtbot)
        m = {"schema_version": 1, "session_date": "2026-06-01T00:00:00",
             "fixes": [{"fix": "brand_new_thing", "revertible": True}]}
        with patch("src.gui.widgets.last_run_card.repolish"):
            card.set_manifest(m)
        assert "Brand New Thing" in _texts(card)


# ── Dashboard.set_last_run visibility toggle ─────────────────────────────────
class TestDashboardSetLastRun:
    def test_toggle_visibility(self, qtbot):
        from src.gui.widgets.dashboard import Dashboard
        with patch("src.gui.widgets.last_run_card.repolish"):
            dash = Dashboard()
            qtbot.addWidget(dash)
            # None / empty → hidden
            dash.set_last_run(None)
            assert dash._last_run_card.isHidden()
            # valid manifest → shown
            dash.set_last_run({
                "schema_version": 1, "session_date": "2026-06-01T00:00:00",
                "fixes": [{"fix": "display", "revertible": True,
                           "before": {"hz": 60}, "after": {"hz": 144}}],
            })
            assert not dash._last_run_card.isHidden()
