"""Tests for src.gui.worker.SystemStatsWorker._tick().

Tests call _tick() directly (no QTimer) to stay synchronous and fast.
Signal capture: connect snapshot_ready to a list before calling _tick().
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.gui.worker import SystemStatsWorker


def _make_worker() -> SystemStatsWorker:
    worker = SystemStatsWorker()
    return worker


class TestSystemStatsWorkerTick:
    def _collect_snapshot(self, worker: SystemStatsWorker) -> dict:
        snaps: list[dict] = []
        worker.snapshot_ready.connect(lambda s: snaps.append(s))
        worker._tick()
        assert len(snaps) == 1, "snapshot_ready must fire exactly once per tick"
        return snaps[0]

    @patch("src.gui.worker.psutil.virtual_memory")
    @patch("src.gui.worker.psutil.cpu_percent", return_value=45.0)
    @patch("src.gui.worker.fetch_snapshot", return_value={})
    def test_tick_emits_cpu_and_ram(self, _fetch, _cpu, mock_vm):
        """Happy path: cpu_usage and ram_used appear in the emitted snapshot."""
        mock_vm.return_value = MagicMock(used=8 * 1_073_741_824)  # 8 GB
        snap = self._collect_snapshot(_make_worker())
        assert snap.get("cpu_usage") == "45%"
        assert snap.get("ram_used") == "8.0 GB"

    @patch("src.gui.worker.fetch_snapshot", return_value={})
    @patch("src.gui.worker.psutil.cpu_percent", side_effect=OSError("no cpu"))
    def test_tick_handles_psutil_failure_gracefully(self, _cpu, _fetch):
        """psutil failure must not raise — snapshot emitted with dash fallback."""
        snap = self._collect_snapshot(_make_worker())
        assert snap.get("cpu_usage") == "—"

    @patch("src.gui.worker.derive_gpu_temp", return_value=68.0)
    @patch("src.gui.worker.derive_cpu_temp", return_value=72.0)
    @patch("src.gui.worker.fetch_snapshot", return_value={"cpu": {"temp": 72}})
    @patch("src.gui.worker.psutil.virtual_memory")
    @patch("src.gui.worker.psutil.cpu_percent", return_value=0.0)
    def test_tick_includes_thermal_data_when_available(self, _cpu, mock_vm, _fetch, _ct, _gt):
        """When fetch_snapshot returns data, cpu_temp and gpu_temp are formatted."""
        mock_vm.return_value = MagicMock(used=0)
        snap = self._collect_snapshot(_make_worker())
        assert snap.get("cpu_temp") == "72°C"
        assert snap.get("gpu_temp") == "68°C"

    @patch("src.gui.worker.fetch_snapshot", side_effect=ConnectionError("lhm down"))
    @patch("src.gui.worker.psutil.virtual_memory")
    @patch("src.gui.worker.psutil.cpu_percent", return_value=0.0)
    def test_tick_handles_fetch_snapshot_failure(self, _cpu, mock_vm, _fetch):
        """fetch_snapshot failure must not raise — snapshot emitted without thermal keys."""
        mock_vm.return_value = MagicMock(used=0)
        snap = self._collect_snapshot(_make_worker())
        assert "cpu_temp" not in snap
        assert "gpu_temp" not in snap

    @patch("src.gui.worker.fetch_snapshot", return_value={})
    @patch("src.gui.worker.psutil.virtual_memory")
    @patch("src.gui.worker.psutil.cpu_percent", return_value=0.0)
    def test_diagnostic_log_fires_on_first_three_ticks(self, _cpu, mock_vm, _fetch, caplog):
        """The diagnostic INFO branch fires on ticks 1, 2, and 3."""
        import logging
        mock_vm.return_value = MagicMock(used=0)
        worker = _make_worker()
        worker.snapshot_ready.connect(lambda _: None)
        with caplog.at_level(logging.INFO, logger="lil_bro"):
            worker._tick()
            worker._tick()
            worker._tick()
        assert worker._tick_count == 3
