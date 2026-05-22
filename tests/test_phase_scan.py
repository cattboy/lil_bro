"""Tests for src.pipeline.phase_scan.ScanPhase.

Covers the fresh-first / snapshot-fallback behaviour that makes a second
pipeline run idempotent (docs/pipeline-rescan-idempotency-plan.md).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.pipeline.base import PipelineContext
from src.pipeline.phase_scan import ScanPhase


def _make_ctx(**kwargs) -> PipelineContext:
    """Build a minimal PipelineContext with a mock LHM sidecar."""
    lhm = MagicMock()
    lhm.start.return_value = True
    defaults = dict(lhm=lhm, thermal=MagicMock())
    defaults.update(kwargs)
    return PipelineContext(**defaults)


def _write_specs(tmp_path, payload: dict) -> str:
    """Write a fresh-scan JSON file and return its path as a string."""
    path = tmp_path / "full_specs.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return str(path)


class TestScanPhaseAlwaysRescans:
    """Regression: the pipeline must re-scan, never reuse a preloaded snapshot."""

    def test_dumps_fresh_even_when_specs_preloaded(self, tmp_path):
        """THE regression test for the re-apply bug.

        A preloaded ctx.specs (the GUI startup snapshot) must NOT short-circuit
        the scan. ScanPhase must call dump_system_specs() every run so a second
        pipeline run sees live state and stops re-proposing already-applied
        fixes. This fails on the pre-fix code (snapshot reused, dump skipped).
        """
        fresh = _write_specs(tmp_path, {"PowerPlan": {"name": "High Performance"}})
        ctx = _make_ctx(specs={"PowerPlan": {"name": "Balanced (STALE)"}})
        with patch("src.pipeline.phase_scan.dump_system_specs", return_value=fresh) as mock_dump, \
             patch("src.pipeline.phase_scan.extract_hardware_summary", return_value={}):
            result = ScanPhase().run(ctx)
        mock_dump.assert_called_once()
        assert ctx.specs == {"PowerPlan": {"name": "High Performance"}}
        assert result.status == "completed"


class TestScanPhaseFallback:
    """1A: a failed fresh dump degrades to the startup snapshot."""

    def test_falls_back_to_snapshot_when_dump_returns_empty(self):
        snapshot = {"PowerPlan": {"name": "snapshot"}}
        ctx = _make_ctx(specs=snapshot)
        with patch("src.pipeline.phase_scan.dump_system_specs", return_value=""), \
             patch("src.pipeline.phase_scan.extract_hardware_summary", return_value={}):
            result = ScanPhase().run(ctx)
        assert ctx.specs == snapshot
        assert result.status == "completed"

    def test_falls_back_to_snapshot_when_fresh_file_corrupt(self, tmp_path):
        snapshot = {"PowerPlan": {"name": "snapshot"}}
        bad = tmp_path / "full_specs.json"
        bad.write_text("NOT JSON {{{", encoding="utf-8")
        ctx = _make_ctx(specs=snapshot)
        with patch("src.pipeline.phase_scan.dump_system_specs", return_value=str(bad)), \
             patch("src.pipeline.phase_scan.extract_hardware_summary", return_value={}):
            result = ScanPhase().run(ctx)
        assert ctx.specs == snapshot
        assert result.status == "completed"

    def test_empty_specs_when_dump_fails_and_no_snapshot(self):
        ctx = _make_ctx()  # specs defaults to {}
        with patch("src.pipeline.phase_scan.dump_system_specs", return_value=""), \
             patch("src.pipeline.phase_scan.extract_hardware_summary", return_value={}):
            result = ScanPhase().run(ctx)
        assert ctx.specs == {}
        assert result.status == "completed"
